"""
Multi-person Arxiv Scraper Server v2

Flask server with in-memory caching for the multi-person digest workflow.
Endpoints:
  GET  /health   - Health check + cache status
  POST /scrape   - Scrape categories, embed abstracts (CPU), cache results
  POST /score    - Score cached papers against a person's keywords
  POST /cleanup  - Free cached papers/embeddings from memory

Uses SPECTER2 (allenai/specter2_base) on CPU for scientific paper embeddings.
"""

from flask import Flask, request, jsonify
import feedparser
import requests
import re
import time
import json
import logging
import gc
import numpy as np

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

# --- In-memory cache (module-level globals) ---
_model = None                  # SentenceTransformer SPECTER2 (CPU)
_paper_cache = {}              # arxiv_id -> paper dict
_paper_embeddings = {}         # arxiv_id -> numpy array (768-dim float32)
_category_papers = {}          # category -> set of arxiv_ids
_cache_time = None             # When the cache was populated


def _get_model():
    """Lazy-load SPECTER2 model on CPU."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        log.info("Loading SPECTER2 model on CPU...")
        start = time.time()
        _model = SentenceTransformer("allenai/specter2_base", device="cpu")
        log.info(f"SPECTER2 loaded in {time.time() - start:.1f}s")
    return _model


def _fetch_rss(category, timeout=30):
    """Fetch paper IDs from an arxiv RSS feed for a given category."""
    url = f"https://rss.arxiv.org/rss/{category}"
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        feed = feedparser.parse(response.content)
    except Exception as e:
        log.warning(f"RSS fetch failed for {category}: {e}")
        return []

    paper_ids = []
    for entry in feed.entries:
        link = entry.get('link', '')
        match = re.search(r'abs/(\d+\.\d+)', link)
        if match:
            paper_ids.append(match.group(1))
    return paper_ids


def _fetch_paper_details(arxiv_ids, batch_size=50, delay=5.0):
    """Fetch full metadata from the arxiv API for a list of paper IDs."""
    import arxiv

    all_papers = {}
    client = arxiv.Client(page_size=batch_size, delay_seconds=delay, num_retries=3)

    # Process in batches
    for i in range(0, len(arxiv_ids), batch_size):
        batch_ids = arxiv_ids[i:i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(arxiv_ids) + batch_size - 1) // batch_size
        log.info(f"  Fetching batch {batch_num}/{total_batches} ({len(batch_ids)} papers)...")
        search = arxiv.Search(id_list=batch_ids)

        for attempt in range(5):
            try:
                results = list(client.results(search))
                break
            except arxiv.HTTPError as e:
                if '429' in str(e) and attempt < 4:
                    wait = 15 * (2 ** attempt)  # 15s, 30s, 60s, 120s
                    log.warning(f"Rate limited on batch {batch_num} (attempt {attempt+1}/5), waiting {wait}s...")
                    time.sleep(wait)
                else:
                    raise
            except Exception as e:
                if attempt < 4:
                    wait = 10 * (attempt + 1)
                    log.warning(f"API error on batch {batch_num} (attempt {attempt+1}/5): {e}, waiting {wait}s...")
                    time.sleep(wait)
                else:
                    raise

        for result in results:
            arxiv_id = result.entry_id.split('/abs/')[-1].split('v')[0]

            pages = None
            comment = getattr(result, 'comment', '') or ''
            pages_match = re.search(r'(\d+)\s*pages?', comment, re.IGNORECASE)
            if pages_match:
                pages = int(pages_match[1])

            reading_time_min = pages * 12 if pages else None

            authors_list = [a.name for a in result.authors]
            if len(authors_list) > 4:
                authors_str = ', '.join(authors_list[:4]) + f', et al. ({len(authors_list)} authors)'
            else:
                authors_str = ', '.join(authors_list)

            all_papers[arxiv_id] = {
                'arxiv_id': arxiv_id,
                'title': result.title.replace('\n', ' ').strip(),
                'abstract': result.summary.replace('\n', ' ').strip(),
                'authors': authors_str,
                'authors_list': authors_list,
                'published': result.published.isoformat(),
                'updated': result.updated.isoformat(),
                'link': f'https://arxiv.org/abs/{arxiv_id}',
                'pdf_link': f'https://arxiv.org/pdf/{arxiv_id}.pdf',
                'pages': pages,
                'reading_time_min': reading_time_min,
                'comment': comment,
            }

        if i + batch_size < len(arxiv_ids):
            log.info(f"  Waiting {delay}s before next batch...")
            time.sleep(delay)

    log.info(f"  Fetched {len(all_papers)} papers total from arxiv API")
    return all_papers


@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'ok',
        'cached_papers': len(_paper_cache),
        'cached_embeddings': len(_paper_embeddings),
        'cached_categories': list(_category_papers.keys()),
        'cache_time': _cache_time,
        'model_loaded': _model is not None,
    })


@app.route('/scrape', methods=['POST'])
def scrape():
    """Scrape arxiv categories, compute abstract embeddings (CPU), cache results."""
    global _paper_cache, _paper_embeddings, _category_papers, _cache_time

    try:
        data = request.get_json(force=True)
        categories = data.get('categories', [])
        if not categories:
            return jsonify({'error': 'No categories provided'}), 400

        start_time = time.time()
        metrics = {}

        # 1. Fetch RSS for each category
        log.info(f"Scraping {len(categories)} categories: {categories}")
        rss_start = time.time()

        category_ids = {}  # category -> list of arxiv_ids
        all_ids = set()

        for cat in categories:
            ids = _fetch_rss(cat)
            category_ids[cat] = ids
            all_ids.update(ids)
            log.info(f"  {cat}: {len(ids)} papers")

        metrics['rss_fetch_time'] = round(time.time() - rss_start, 2)
        metrics['total_unique_papers'] = len(all_ids)
        log.info(f"Total unique papers: {len(all_ids)}")

        if not all_ids:
            return jsonify({
                'error': 'No papers found in RSS feeds',
                'papers_by_category': {},
                'total_unique_papers': 0,
                'metrics': metrics,
            })

        # 2. Fetch full metadata from arxiv API
        log.info("Fetching paper details from arxiv API...")
        api_start = time.time()
        papers = _fetch_paper_details(list(all_ids))
        metrics['api_fetch_time'] = round(time.time() - api_start, 2)
        metrics['papers_fetched'] = len(papers)
        log.info(f"Fetched {len(papers)} paper details")

        # 3. Build category -> arxiv_id mapping (only for papers we actually fetched)
        cat_papers = {}
        for cat, ids in category_ids.items():
            cat_papers[cat] = set(aid for aid in ids if aid in papers)

        # 4. Compute embeddings with SPECTER2 on CPU
        log.info("Computing SPECTER2 embeddings on CPU...")
        embed_start = time.time()
        model = _get_model()

        paper_ids_list = list(papers.keys())
        abstracts = [papers[pid]['abstract'] for pid in paper_ids_list]
        embeddings = model.encode(abstracts, normalize_embeddings=True, show_progress_bar=False, batch_size=32)
        metrics['embedding_time'] = round(time.time() - embed_start, 2)
        log.info(f"Embeddings computed in {metrics['embedding_time']}s for {len(abstracts)} papers")

        # 5. Update cache
        _paper_cache = papers
        _paper_embeddings = {pid: embeddings[i] for i, pid in enumerate(paper_ids_list)}
        _category_papers = cat_papers
        _cache_time = time.strftime('%Y-%m-%dT%H:%M:%S')

        metrics['total_time'] = round(time.time() - start_time, 2)

        # Build per-category counts for response
        papers_by_category = {}
        for cat, id_set in cat_papers.items():
            papers_by_category[cat] = len(id_set)

        return jsonify({
            'papers_by_category': papers_by_category,
            'total_unique_papers': len(papers),
            'metrics': metrics,
        })

    except Exception as e:
        import traceback
        log.error(f"Scrape error: {traceback.format_exc()}")
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500


@app.route('/score', methods=['POST'])
def score():
    """Score cached papers against a person's keywords. Return top N."""
    try:
        data = request.get_json(force=True)
        keywords = data.get('keywords', '')
        person_categories = data.get('categories', [])
        top_n = data.get('top_n', 10)

        if not keywords:
            return jsonify({'error': 'No keywords provided'}), 400

        if not _paper_cache:
            return jsonify({'error': 'No papers cached. Call /scrape first.'}), 400

        start_time = time.time()

        # 1. Filter papers to person's categories
        relevant_ids = set()
        if person_categories:
            for cat in person_categories:
                if cat in _category_papers:
                    relevant_ids.update(_category_papers[cat])
        else:
            # No category filter = all papers
            relevant_ids = set(_paper_cache.keys())

        if not relevant_ids:
            return jsonify({
                'papers': [],
                'total_in_categories': 0,
                'scoring_time': 0,
            })

        # 2. Embed keywords on CPU
        model = _get_model()
        keyword_embedding = model.encode([keywords], normalize_embeddings=True, show_progress_bar=False)[0]

        # 3. Compute cosine similarity for filtered papers
        scored_papers = []
        for pid in relevant_ids:
            if pid in _paper_embeddings:
                sim = float(np.dot(keyword_embedding, _paper_embeddings[pid]))
                paper = dict(_paper_cache[pid])  # copy
                paper['relevance_score'] = round(sim, 4)

                # Track which of this person's categories the paper belongs to
                paper_cats = []
                for cat in person_categories:
                    if cat in _category_papers and pid in _category_papers[cat]:
                        paper_cats.append(cat)
                paper['categories'] = paper_cats

                scored_papers.append(paper)

        # 4. Sort by relevance score and take top N
        scored_papers.sort(key=lambda x: x['relevance_score'], reverse=True)
        top_papers = scored_papers[:top_n]

        for rank, paper in enumerate(top_papers, 1):
            paper['rank'] = rank

        scoring_time = round(time.time() - start_time, 4)

        return jsonify({
            'papers': top_papers,
            'total_in_categories': len(relevant_ids),
            'scoring_time': scoring_time,
        })

    except Exception as e:
        import traceback
        log.error(f"Score error: {traceback.format_exc()}")
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500


@app.route('/cleanup', methods=['POST'])
def cleanup():
    """Free cached papers and embeddings from memory."""
    global _paper_cache, _paper_embeddings, _category_papers, _cache_time, _model

    papers_freed = len(_paper_cache)
    embeddings_freed = len(_paper_embeddings)

    _paper_cache = {}
    _paper_embeddings = {}
    _category_papers = {}
    _cache_time = None

    # Also unload the model to free ~500MB RAM
    if _model is not None:
        del _model
        _model = None

    gc.collect()

    log.info(f"Cleanup: freed {papers_freed} papers, {embeddings_freed} embeddings, unloaded model")

    return jsonify({
        'status': 'cleaned',
        'papers_freed': papers_freed,
        'embeddings_freed': embeddings_freed,
        'model_unloaded': True,
    })


if __name__ == '__main__':
    print("=" * 60)
    print("Arxiv Scraper Server v2 (Multi-Person)")
    print("=" * 60)
    print()
    print("Endpoints:")
    print("  GET  http://localhost:5680/health    - Health check + cache status")
    print("  POST http://localhost:5680/scrape    - Scrape categories & embed")
    print("  POST http://localhost:5680/score     - Score papers for a person")
    print("  POST http://localhost:5680/cleanup   - Free cache & model")
    print()
    print("Model: SPECTER2 (allenai/specter2_base) on CPU")
    print("Starting server on port 5680...")
    print("=" * 60)

    app.run(host='0.0.0.0', port=5680, debug=False, threaded=True)
