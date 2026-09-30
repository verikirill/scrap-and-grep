"""Personal recommendations.

A reader is described by facets: the interests of their profiles, their resume
and the themes learned from what they liked, saved and opened. Articles are
matched against every facet, the evidence is blended into one score, and the
top of the list is re-ranked for variety. What the reader rejected forms
"avoid" facets that push similar articles down.

    signals -> taste (facets) -> evidence per article (SQL) -> score
            -> variety re-rank + exploration slots -> feed with reasons

The scoring and re-ranking are pure functions (taste.py, ranking.py); the
database and the cache live in store.py and service.py.
"""
