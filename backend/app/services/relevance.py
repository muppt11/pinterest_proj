"""When is a text search a real match? Shared by search and the assistant's search tool.

Mean cosine of the top RELEVANCE_WINDOW results. Measured on the real index (2026-10-28): 13 clothing
queries scored 0.232–0.269, 13 non-clothing/gibberish queries 0.069–0.211; 0.22 sits in the gap.
The eval report re-checks it on held-out queries.
"""

MIN_TEXT_RELEVANCE = 0.22
RELEVANCE_WINDOW = 10
