"""A learned ranker for the feed, trained on reader events.

The hand-tuned blend in `radar.recsys.ranking` scores every article. A model
trained on what readers did with what they were shown may reorder the best
of them; it is switched on only when it beats the hand blend on days it has
not seen, and only for a share of readers, so the two can be compared.
"""
