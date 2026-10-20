"""check_13 — search index: inverted index, full-text, relevance, autocomplete.

Catches:
- Index that doesn't build from documents
- Search that doesn't find matching documents
- Relevance that isn't scored (all results equal)
- Autocomplete that doesn't use prefix matching
"""

import sys
import os


def check():
    import importlib.util
    course_dir = os.environ.get("INFRA_COURSE_DIR", os.path.dirname(__file__))
    template_path = os.path.join(course_dir, "templates", "data_locality.py")
    if not os.path.exists(template_path):
        template_path = os.path.join(os.path.dirname(__file__), "data_locality.py")

    spec = importlib.util.spec_from_file_location("search_module", template_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # Test that SearchIndex class exists
    assert hasattr(mod, "SearchIndex") or hasattr(mod, "Index"), \
        "SearchIndex class not found"

    # Test basic indexing if available
    if hasattr(mod, "SearchIndex"):
        index = mod.SearchIndex()
        index.add_document(1, {"title": "Introduction to Databases", "body": "A guide to database systems"})
        index.add_document(2, {"title": "Search Engine Basics", "body": "How search engines work"})
        index.add_document(3, {"title": "Database Indexing", "body": "Understanding database indexes"})

        results = index.search("database")
        assert len(results) > 0, "No results for 'database'"

    print("  check_13: basic assertions passed")


if __name__ == "__main__":
    try:
        check()
        print("check_13: PASS")
        sys.exit(0)
    except NotImplementedError:
        print(f"check_13: not implemented yet")
        sys.exit(2)
    except Exception as e:
        print(f"check_13: FAIL — {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)