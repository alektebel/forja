# Search Index — Complex

## 1. What problem does it solve?

A database query: `WHERE name LIKE '%john%'`
This is a table scan (or index scan) — O(N) or O(log N) with B-tree.
For full-text search (fuzzy matching, relevance scoring, faceted navigation),
a traditional index is inadequate.

A search index (inverted index) maps each word to the documents containing it:
```
"search" → [doc_1, doc_3, doc_7]
"index" →  [doc_1, doc_2, doc_4, doc_7]
"data" →   [doc_2, doc_3, doc_5]
```

**The job:** index text documents and support fast full-text search:
fuzzy matching, relevance scoring, faceted navigation, autocomplete,
with performance that scales.

## 2. How does it work?

### Inverted index (core data structure)

| Term | Document IDs | Term Frequency (TF) |
|---|---|---|
| search | {1, 3, 7} | {doc1:2, doc3:1, doc7:3} |
| index | {1, 2, 4, 7} | {doc1:1, doc2:5, doc4:2, doc7:1} |
| data | {2, 3, 5} | {doc2:3, doc3:1, doc5:2} |

Search "search index":
- `doc1`: appears in both → score = TF(1,search) × TF(1,index) = 2 × 1 = 2
- `doc7`: appears in both → score = TF(7,search) × TF(7,index) = 3 × 1 = 3
- Sort by score: doc7 (3) > doc1 (2)

### TF-IDF (relevance scoring)

```
score(doc, query) = Σ(term in query) TF(term, doc) × IDF(term)

IDF(term) = log(total_documents / documents_containing_term)
```

- High TF (term appears many times in document) → higher score
- High IDF (term is rare across all documents) → higher score

### Tokenization

Input text → tokens:
1. **Lowercase**: "Hello" → "hello"
2. **Stemming/lemmatization**: "searching" → "search"
3. **Stop words**: remove "the", "and", "of"
4. **N-grams**: "elastic" → ["el", "la", as, st", "ti", "ic", "c"]

### Faceted navigation

Index metadata alongside text:
```json
{
  "title": "Introduction to Databases",
  "author": "Jane Smith",
  "year": 2020,
  "category": "Computer Science",
  "price": 49.99,
  "body": "A comprehensive guide to database systems..."
}
```

Facets: `{author: ["Jane Smith", "John Doe"], category: ["Computer Science", "Math"]}`

### Autocomplete / prefix search

Two approaches:
1. **Prefix index**: index all n-grams; query "elas" → [doc with "elastic", "elasticsearch"]
2. **Trie (prefix tree)**: store all terms in a trie; traverse with query prefix

## 3. Real implementations

| Implementation | Type | Notes |
|---|---|---|
| **Elasticsearch** | Full-text search | Based on Lucene; distributed; REST API; most popular |
| **Apache Lucene** | Search library | Java library; Elasticsearch runs on Lucene |
| **Meilisearch** | Lightweight search | Rust-based; fast; simple API; great for small-medium scale |
| **Typesense** | Real-time search | Fork of Typesense (C++ → Rust); fast; simple |
| **OpenSearch** | Fork of Elasticsearch | AWS fork after Elasticsearch changed license; open-source |
| **Whoosh** | Python search library | Pure Python; lightweight; good for small apps |

## 4. Trade-offs

| Decision | Option A | Option B | When to choose B |
|---|---|---|---|
| Index type | Inverted index (full-text) | B-tree (structured) | Text search → inverted; key lookup → B-tree |
| Search | Exact match | Fuzzy (edit distance) | Exact data → exact; product names → fuzzy |
| Relevance | TF-IDF | BM25 | TF-IDF is simple; BM25 handles term frequency better |
| Scale | Single-node (Meilisearch) | Distributed (Elasticsearch) | Small dataset → single-node; millions of docs → distributed |
| Autocomplete | N-gram index | Trie | Simple → n-gram; large vocab → trie |

## 5. Exercises

1. **Inverted index**: Build an inverted index from a list of documents; support term → doc mapping.
2. **Search engine**: Given a query, compute TF-IDF scores and return top-K results.
3. **Fuzzy search**: Support edit distance ≤ 1 (Levenshtein); return all terms within distance 1 of the query.
4. **Faceted search**: Index documents with metadata; return facets (count per category/author) alongside results.
5. **Autocomplete**: Implement a trie; traverse with query prefix; return top-K matching terms.

## 6. References

- [Elasticsearch documentation](https://www.elastic.co/guide/en/elasticsearch/reference/current/)
- [TF-IDF (Wikipedia)](https://en.wikipedia.org/wiki/Tf–idf)
- [BM25 algorithm (Robertson et al., 1994)](https://en.wikipedia.org/wiki/Okapi_BM25)
- [Lucene architecture](https://lucene.apache.org/core/overview.html)
- [Meilisearch documentation](https://docs.meilisearch.com/)
- [Inverted index (Wikipedia)](https://en.wikipedia.org/wiki/Inverted_index)