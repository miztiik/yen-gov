# Electoral clean-start diff receipt (B2b.5.0c-2)

Evidence for the LGD-snapshot override of the prior taxonomy-derived
`electoral.csv`, committed BEFORE 0d-del deletes any old artifact
(sub-plan section 0c.3). The verdict line classifies the override; the
word "corrupted" is never used without this evidence.

- Verdict: **minor-membership-shift**
- Row delta: -56 (old 4451 -> new 4395)
- Id overlap vs new: 0.9804 (old-only 142, new-only 86)

```json
{
  "cardinality_new": {
    "andhra-pradesh": {
      "ac": 173,
      "pc": 25
    },
    "arunachal-pradesh": {
      "ac": 60,
      "pc": 2
    },
    "assam": {
      "ac": 125,
      "pc": 14
    },
    "bihar": {
      "ac": 241,
      "pc": 40
    },
    "chhattisgarh": {
      "ac": 90,
      "pc": 11
    },
    "dadra-and-nagar-haveli-and-daman-and-diu": {
      "pc": 2
    },
    "goa": {
      "ac": 39,
      "pc": 2
    },
    "gujarat": {
      "ac": 178,
      "pc": 26
    },
    "haryana": {
      "ac": 85,
      "pc": 10
    },
    "himachal-pradesh": {
      "ac": 68,
      "pc": 4
    },
    "jammu-and-kashmir": {
      "ac": 77,
      "pc": 5
    },
    "jharkhand": {
      "ac": 78,
      "pc": 14
    },
    "karnataka": {
      "ac": 208,
      "pc": 28
    },
    "kerala": {
      "ac": 138,
      "pc": 20
    },
    "ladakh": {
      "pc": 1
    },
    "lakshadweep": {
      "pc": 1
    },
    "madhya-pradesh": {
      "ac": 229,
      "pc": 29
    },
    "maharashtra": {
      "ac": 267,
      "pc": 47
    },
    "manipur": {
      "ac": 60,
      "pc": 2
    },
    "meghalaya": {
      "ac": 56,
      "pc": 2
    },
    "mizoram": {
      "ac": 32,
      "pc": 1
    },
    "nagaland": {
      "ac": 57,
      "pc": 1
    },
    "odisha": {
      "ac": 146,
      "pc": 21
    },
    "puducherry": {
      "ac": 24,
      "pc": 1
    },
    "punjab": {
      "ac": 116,
      "pc": 13
    },
    "rajasthan": {
      "ac": 187,
      "pc": 25
    },
    "sikkim": {
      "ac": 29,
      "pc": 1
    },
    "tamil-nadu": {
      "ac": 232,
      "pc": 39
    },
    "telangana": {
      "ac": 109,
      "pc": 17
    },
    "tripura": {
      "ac": 60,
      "pc": 2
    },
    "uttar-pradesh": {
      "ac": 377,
      "pc": 79
    },
    "uttarakhand": {
      "ac": 69,
      "pc": 5
    },
    "west-bengal": {
      "ac": 255,
      "pc": 40
    }
  },
  "cardinality_old": {
    "andaman-and-nicobar": {
      "pc": 1
    },
    "andhra-pradesh": {
      "ac": 175,
      "pc": 25
    },
    "arunachal-pradesh": {
      "ac": 60,
      "pc": 2
    },
    "assam": {
      "ac": 126,
      "pc": 14
    },
    "bihar": {
      "ac": 243,
      "pc": 40
    },
    "chandigarh": {
      "ac": 1,
      "pc": 1
    },
    "chhattisgarh": {
      "ac": 90,
      "pc": 11
    },
    "dadra-and-nagar-haveli-and-daman-and-diu": {
      "pc": 2
    },
    "goa": {
      "ac": 40,
      "pc": 2
    },
    "gujarat": {
      "ac": 181,
      "pc": 26
    },
    "haryana": {
      "ac": 90,
      "pc": 10
    },
    "himachal-pradesh": {
      "ac": 68,
      "pc": 4
    },
    "jammu-and-kashmir": {
      "ac": 79,
      "pc": 5
    },
    "jharkhand": {
      "ac": 65,
      "pc": 14
    },
    "karnataka": {
      "ac": 223,
      "pc": 28
    },
    "kerala": {
      "ac": 140,
      "pc": 20
    },
    "madhya-pradesh": {
      "ac": 225,
      "pc": 29
    },
    "maharashtra": {
      "ac": 287,
      "pc": 48
    },
    "manipur": {
      "ac": 57,
      "pc": 2
    },
    "meghalaya": {
      "ac": 57,
      "pc": 2
    },
    "mizoram": {
      "ac": 40,
      "pc": 1
    },
    "nagaland": {
      "ac": 60,
      "pc": 1
    },
    "odisha": {
      "ac": 147,
      "pc": 21
    },
    "puducherry": {
      "ac": 27,
      "pc": 1
    },
    "punjab": {
      "ac": 116,
      "pc": 13
    },
    "rajasthan": {
      "ac": 194,
      "pc": 25
    },
    "sikkim": {
      "ac": 30,
      "pc": 1
    },
    "tamil-nadu": {
      "ac": 232,
      "pc": 39
    },
    "telangana": {
      "ac": 95,
      "pc": 17
    },
    "tripura": {
      "ac": 60,
      "pc": 2
    },
    "uttar-pradesh": {
      "ac": 393,
      "pc": 80
    },
    "uttarakhand": {
      "ac": 67,
      "pc": 5
    },
    "west-bengal": {
      "ac": 250,
      "pc": 41
    }
  },
  "id_overlap": {
    "common": 4309,
    "new_only": 86,
    "old_only": 142,
    "overlap_ratio_vs_new": 0.9804
  },
  "name_mismatch_buckets": {},
  "name_mismatch_sample": [],
  "new_csv": "datasets/data/entities/electoral.csv",
  "old_csv": ".runtime/electoral_old.csv",
  "orphans": {
    "new_only_sample": [
      "ac/jammu-and-kashmir/50",
      "ac/jammu-and-kashmir/64",
      "ac/jharkhand/2141",
      "ac/jharkhand/2144",
      "ac/jharkhand/2153",
      "ac/jharkhand/2155",
      "ac/jharkhand/2157",
      "ac/jharkhand/2169",
      "ac/jharkhand/2183",
      "ac/jharkhand/2184",
      "ac/jharkhand/2191",
      "ac/jharkhand/2196",
      "ac/jharkhand/2202",
      "ac/jharkhand/2204",
      "ac/jharkhand/2205",
      "ac/jharkhand/2206",
      "ac/jharkhand/2207",
      "ac/madhya-pradesh/2502",
      "ac/madhya-pradesh/2561",
      "ac/madhya-pradesh/2587",
      "ac/madhya-pradesh/2596",
      "ac/madhya-pradesh/2598",
      "ac/maharashtra/2933",
      "ac/manipur/1545",
      "ac/manipur/1553"
    ],
    "old_only_sample": [
      "ac/andhra-pradesh/3230",
      "ac/andhra-pradesh/3430",
      "ac/assam/1765",
      "ac/bihar/1273",
      "ac/bihar/1277",
      "ac/chandigarh/273",
      "ac/goa/3707",
      "ac/gujarat/2689",
      "ac/gujarat/2769",
      "ac/gujarat/2830",
      "ac/haryana/363",
      "ac/haryana/364",
      "ac/haryana/384",
      "ac/haryana/395",
      "ac/haryana/415",
      "ac/jammu-and-kashmir/37",
      "ac/jammu-and-kashmir/65",
      "ac/jammu-and-kashmir/68",
      "ac/jammu-and-kashmir/70",
      "ac/jharkhand/2178",
      "ac/jharkhand/2214",
      "ac/karnataka/3462",
      "ac/karnataka/3463",
      "ac/karnataka/3486",
      "ac/karnataka/3497"
    ]
  },
  "row_counts": {
    "delta": -56,
    "new": 4395,
    "old": 4451
  },
  "verdict": "minor-membership-shift"
}
```
