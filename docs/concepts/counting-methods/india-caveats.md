# India-specific caveats

**Last Updated**: 2026-06-09

Indian elections sit on a substrate the textbook voting-theory papers
don't model. This page lists six structural features that make
European or US comparisons fragile. Read this BEFORE drawing a
conclusion from any of the methods on the previous page.

These factors don't make the Election Studio's outputs wrong - they
shape what those outputs reveal and what they conceal.

## Caste arithmetic and ballot transfer

The proportional-transfer rules (IRV proportional, TRS Round 2
proportional, Borda) assume voters whose first preference is eliminated
distribute their second preference proportional to surviving
candidates' shares. In Indian practice, caste alignment is the single
strongest predictor of vote transfer: a Dalit voter whose preferred
candidate is eliminated is more likely to support an INDIA-bloc
candidate than an NDA candidate, almost regardless of which surviving
candidate has more first-preference votes in their AC.

This caveat applies most strongly to: **IRV (proportional transfer)**,
**TRS Round 2 (proportional)**, **Borda Count**. The alliance variants
of IRV and TRS are an attempt to bracket this effect at the upper
bound (100% bloc discipline) versus the lower bound (zero discipline
in the proportional variants). The truth lives between them.

## NOTA as abstention vs preference

The Election Studio treats NOTA as a legitimate ballot mark but
excludes it from transfer rounds (NOTA cannot inherit eliminated
votes; NOTA cannot be eliminated). India's NOTA was introduced in 2013
per a Supreme Court ruling; in practice NOTA polls 0.5-1.5% of votes
in most ACs.

The interpretation question is structural: a NOTA voter is rejecting
ALL candidates on the ballot, not expressing a ranked preference
between them. Treating NOTA as "abstention" (the Election Studio's
default) is the conservative choice. Treating it as "preference for
none of the surviving candidates" would zero out NOTA voters' impact
on every transfer round, which has the same numerical effect.

This caveat applies most strongly to: every Medium-Validity method
(NOTA exclusion affects transfer arithmetic) and the proportional-PR
methods (NOTA exclusion from the divisor mildly inflates allocated
parties' seat shares).

## Independents and the alliance-tier collapse

The alliance-aware methods (IRV alliance-transfer, TRS Round 2
alliance) look up each party in `datasets/data/entities/party_alliances.csv`
keyed by `(party_id, period_label)`. Independent candidates (party_id =
`parties.IN.IND`) have no alliance row; the rules treat them as
unaligned and fall back to proportional transfer for that candidate's
votes.

In practice, Indian independents are often de facto alliance partners
- a candidate denied the official symbol who contests as an
independent but supports the alliance. The Election Studio cannot
infer this affiliation from the data; the proportional fallback is the
honest treatment.

This caveat applies most strongly to: **IRV (alliance-transfer)** and
**TRS Round 2 (alliance)**.

## Electorate-size variance across ACs

Indian Assembly Constituencies range from ~50,000 voters (remote
North-East ACs) to ~3,000,000 voters (urban metros, undelimited since
2008). FPTP weights each AC equally regardless of electorate size, and
so do most of the Election Studio's counting rules. The Borda Count
goes further: one rank-position unit per AC, regardless of how many
voters that AC contains.

Under Borda this means a state with crowded fields in small ACs
(Nagaland, Mizoram - typically 5-8 candidates per AC) implicitly
amplifies versus a state with two-horse races in large ACs (large
chunks of UP, Bihar). The Borda result for a state-level question is
mathematically clean but the small-AC weighting bias is structural.

This caveat applies most strongly to: **Borda Count** (explicit
weighting choice) and **MMP** (the list-tier allocation depends on
state-wide totals where small ACs and big ACs contribute equally).

## Multi-cornered contests (4+ serious candidates)

Many Indian races are genuinely multi-cornered: a 3-way contest in
West Bengal between TMC, BJP, and INDIA bloc; a 4-way contest in
Bihar between NDA, RJD, INC, and AIMIM. The Medium-Validity methods
shine in these races - they show the FPTP plurality is structurally
narrow and the eliminated bloc could flip the seat.

The fascinating limit: in a 4+ candidate race, the proportional
transfer rule and the alliance transfer rule typically produce
DIFFERENT winners. The two views are most informative when read
together - the divergence locates the seats where alliance discipline
matters most.

This caveat applies most strongly to: the four alliance/non-alliance
pairs (**IRV** and **TRS Round 2** in both variants).

## Booth-level capture and the recount question

The Election Studio reads the official Election Commission results as
published. It does NOT model:

- Booth-level vote capture (where one party physically controls a
  polling booth and inflates its own votes).
- Recount-altered results (where the original published count was
  later revised on petition).
- EVM tampering allegations (the Election Studio takes the official
  result as the data; the simulator cannot reason about ballot
  integrity).

This is a deliberate boundary. The Election Studio explores "what
COUNTING method would produce what result", holding the underlying
ballot data constant. Questions about ballot integrity belong in a
different conversation; the Election Commission, courts, and electoral
observers are the appropriate venues.

This caveat applies most strongly to: every method. The Election
Studio is silent on questions of ballot validity.

## Further reading

- [Counting methods: overview](overview.md) - the three theoretical
  constraints + the practical-priority trade-offs.
- [Counting methods: derivability](derivability.md) - which methods
  are mechanically derivable and which require an explicit
  assumption.
- Election Commission of India, *Manual on Electoral Rolls*.
- NCRWC Report (2002), Chapter 4: Electoral Reforms.
