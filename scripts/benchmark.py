#!/usr/bin/env python3
"""Performance benchmarks for poetry-mcp server.

Measures:
- Catalog sync time
- Search performance
- Tag search performance
- Memory usage
"""

import sys
import time
import tracemalloc
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from poetry_mcp.config import load_config
from poetry_mcp.catalog.catalog import Catalog


def format_time(seconds: float) -> str:
    """Format time in human-readable format."""
    if seconds < 1:
        return f"{seconds * 1000:.1f}ms"
    return f"{seconds:.2f}s"


def format_memory(bytes: int) -> str:
    """Format memory in human-readable format."""
    mb = bytes / (1024 * 1024)
    return f"{mb:.1f}MB"


def benchmark_catalog_sync():
    """Benchmark catalog sync performance."""
    print("\n📊 Benchmark: Catalog Sync")
    print("=" * 50)

    config = load_config()
    catalog = Catalog(
        vault_root=config.vault.path,
        exclude_dirs=config.vault.exclude_catalog_dirs,
        custom_states=config.vault.custom_states,
    )

    # Measure sync time
    start = time.time()
    result = catalog.sync(force_rescan=True)
    elapsed = time.time() - start

    print(f"  Poems indexed: {result.total_poems}")
    print(f"  Time: {format_time(elapsed)}")
    print(f"  Target: <5s for 381 poems")
    print(f"  Status: {'✅ PASS' if elapsed < 5.0 else '❌ FAIL'}")

    return catalog


def benchmark_text_search(catalog: Catalog):
    """Benchmark text search performance."""
    print("\n📊 Benchmark: Text Search")
    print("=" * 50)

    test_queries = ["water", "river", "stone", "sky", "memory"]

    total_time = 0
    for query in test_queries:
        start = time.time()
        results = catalog.index.search_content(query, case_sensitive=False)
        elapsed = time.time() - start
        total_time += elapsed

        print(f"  Query '{query}': {format_time(elapsed)} ({len(results[:20])} results)")

    avg_time = total_time / len(test_queries)
    print(f"\n  Average: {format_time(avg_time)}")
    print(f"  Target: <500ms")
    print(f"  Status: {'✅ PASS' if avg_time < 0.5 else '❌ FAIL'}")


def benchmark_tag_search(catalog: Catalog):
    """Benchmark tag search performance."""
    print("\n📊 Benchmark: Tag Search")
    print("=" * 50)

    # Get some actual tags from the catalog
    all_tags = set()
    for poem in catalog.index.all_poems[:100]:  # Sample first 100 poems
        all_tags.update(poem.tags)

    test_tags = list(all_tags)[:5]  # Use first 5 unique tags

    if not test_tags:
        print("  ⚠️  No tags found in catalog")
        return

    total_time = 0
    for tag in test_tags:
        start = time.time()
        results = catalog.index.get_by_tags([tag], match_mode="all")
        elapsed = time.time() - start
        total_time += elapsed

        print(f"  Tag '{tag}': {format_time(elapsed)} ({len(results[:20])} results)")

    avg_time = total_time / len(test_tags)
    print(f"\n  Average: {format_time(avg_time)}")
    print(f"  Target: <50ms")
    print(f"  Status: {'✅ PASS' if avg_time < 0.05 else '❌ FAIL'}")


def benchmark_memory_usage(catalog: Catalog):
    """Benchmark memory usage."""
    print("\n📊 Benchmark: Memory Usage")
    print("=" * 50)

    tracemalloc.start()

    # Force a sync to ensure everything is loaded
    catalog.sync(force_rescan=True)

    # Get current memory usage
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    print(f"  Current: {format_memory(current)}")
    print(f"  Peak: {format_memory(peak)}")
    print(f"  Target: <200MB for 381 poems")
    print(f"  Status: {'✅ PASS' if peak < 200 * 1024 * 1024 else '❌ FAIL'}")


def main():
    """Run all benchmarks."""
    print("\n" + "=" * 50)
    print("  Poetry MCP Performance Benchmarks")
    print("=" * 50)

    try:
        # Run benchmarks
        catalog = benchmark_catalog_sync()
        benchmark_text_search(catalog)
        benchmark_tag_search(catalog)
        benchmark_memory_usage(catalog)

        print("\n" + "=" * 50)
        print("  Benchmarks Complete")
        print("=" * 50 + "\n")

    except Exception as e:
        print(f"\n❌ Error running benchmarks: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
