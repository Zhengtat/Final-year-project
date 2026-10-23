# CR-007 STOP 2: IIR concept extraction v3

Dev = IIR chapters 1-3 (13 sections, FACE's own text); test = chapters 4-16 rebuilt by the promoted scraper, 70 sections. Bulk tier, cached, every call through `LLMClient`. Prompt files: `prompts/concept_extraction/v2.md` (frozen) and `v3x.md` (experiment template; blocks in `blocks_v3x/`). No gold term appears in any prompt example.

## 1. Scraper and gold-presence gate

The scraper now lives in `src/cumap/data/iir_scrape.py` (tests: tree walk, subtree/annotated-descendant rule, intro rule, gate). Of 73 annotated test sections **70 passed the 90% gold-presence gate**; variant A (own page + un-annotated descendants, chapter intro on the first section of a chapter without a bare annotation) sufficed for all of them; variant B (ancestor pages) never rescued a section.

Excluded and listed, never scored: `iir_11` (gold presence 89.7% below the 90% gate; 29 gold concepts); `iir_13_5` (gold presence 89.7% below the 90% gate; 58 gold concepts); `iir_14_5` (gold presence 85.3% below the 90% gate; 34 gold concepts). Two of the three are 0.3 points under the gate.

## 2. Dev ablation (E1-E5 singly on top of v2)

| variant | calls/section | predicted | exact P / R / F1 (micro) | lenient P / R / F1 (micro) | exact macro F1 | lenient macro F1 |
|---|---|---|---|---|---|---|
| v2 | 1 | 404 | 0.535 / 0.445 / **0.486** | 0.673 / 0.561 / **0.612** | 0.487 | 0.608 |
| E1 | 1 | 574 | 0.434 / 0.513 / **0.470** | 0.561 / 0.664 / **0.608** | 0.465 | 0.597 |
| E2-union | 3 | 747 | 0.371 / 0.571 / **0.450** | 0.461 / 0.709 / **0.558** | 0.452 | 0.561 |
| E2-vote2 | 3 | 410 | 0.537 / 0.454 / **0.492** | 0.629 / 0.532 / **0.577** | 0.487 | 0.572 |
| E3 | 1 | 585 | 0.470 / 0.567 / **0.514** | 0.600 / 0.724 / **0.656** | 0.513 | 0.648 |
| E4 | 1 | 471 | 0.469 / 0.456 / **0.462** | 0.611 / 0.594 / **0.603** | 0.462 | 0.595 |
| E5 | 1 | 452 | 0.500 / 0.466 / **0.482** | 0.642 / 0.598 / **0.619** | 0.485 | 0.616 |
| E3+E5 | 1 | 651 | 0.433 / 0.581 / **0.496** | 0.558 / 0.748 / **0.639** | 0.495 | 0.631 |

What each is: E1 code-book in the prompt; E2 three varied runs (union / >= 2-of-3 vote); E3 consistency propagation on v2 ($0 post-processing: a concept accepted anywhere is also tagged, role `mentioned`, source `propagation`, wherever a longest-match mention occurs); E4 two few-shot examples from other dev sections; E5 granularity rule; E3+E5 the pre-registered combination.

Recall by gold n-gram length (lenient) and precision by role (lenient):

| variant | recall 1 / 2 / 3 / 4-gram | precision defined / used / mentioned |
|---|---|---|
| v2 | 0.47 / 0.61 / 0.63 / 0.50 | 0.79 / 0.57 / 0.63 |
| E1 | 0.54 / 0.72 / 0.79 / 0.62 | 0.79 / 0.50 / 0.43 |
| E2-union | 0.62 / 0.75 / 0.81 / 0.62 | 0.58 / 0.40 / 0.40 |
| E2-vote2 | 0.44 / 0.59 / 0.63 / 0.12 | 0.75 / 0.58 / 0.46 |
| E3 | 0.74 / 0.72 / 0.70 / 0.62 | 0.79 / 0.57 / 0.49 |
| E4 | 0.51 / 0.63 / 0.68 / 0.62 | 0.76 / 0.56 / 0.45 |
| E5 | 0.50 / 0.64 / 0.75 / 0.38 | 0.78 / 0.56 / 0.53 |
| E3+E5 | 0.74 / 0.75 / 0.81 / 0.38 | 0.78 / 0.56 / 0.41 |

## 3. Selection by the pre-registered rule

Rule (DECISIONS.md, fixed before any run): highest dev **lenient micro F1**; candidates within 0.02 of the best go to the simpler (fewer calls per section, then fewer components). The combination rule (every single that beats v2 by more than 0.005) was also fixed beforehand.

- Beat v2 (0.612) by more than 0.005: E3 (+0.044), E5 (+0.007). So the combination run was E3+E5.
- Best dev lenient micro F1: **E3 0.656**; within 0.02 of it: E3, E3+E5.
- **Chosen v3 = E3**: the v2 prompt unchanged plus consistency propagation (E3). It needs no new prompt file, so `v3` is a pipeline version (prompt v2 + propagation), not a new prompt version.

Honest reading of the ablation: everything that changes the prompt (E1, E4, E5) moved dev F1 by less than 0.01 either way; the three-run union (E2) lost about 0.05 (recall up, precision far down); the only clear gain is the free post-processing step E3. That gain is recall of terms the model already accepted elsewhere, so it pushes precision down (0.673 to 0.600) and recall up (0.561 to 0.724).

## 4. Full IIR test split (each version was meant to run once; see section 5)

| version | calls/section | predicted | exact P / R / F1 (micro) | lenient P / R / F1 (micro) | exact macro F1 | lenient macro F1 |
|---|---|---|---|---|---|---|
| v2 | 1 | 2101 | 0.520 / 0.371 / **0.433** | 0.684 / 0.487 / **0.569** | 0.443 | 0.580 |
| v3 (v2 + propagation) | 1 | 4081 | 0.417 / 0.580 / **0.485** | 0.544 / 0.756 / **0.633** | 0.489 | 0.642 |

Test run: `test_0d5035ce`. Headline (owner's rule): **v3 exact micro F1 on the full test split = 0.485**, compared exact-to-exact with FACE's published micro F1 0.76 (supervised, 5-fold CV on the same book, so not like-for-like) and with the earlier chapters-4/6/9-only v2 result 0.474.

Recall by gold n-gram length on test (lenient) and precision by role:

| version | recall 1 / 2 / 3 / 4-gram | precision defined / used / mentioned |
|---|---|---|
| v2 | 0.38 / 0.56 / 0.49 / 0.42 | 0.75 / 0.65 / 0.63 |
| v3 | 0.79 / 0.79 / 0.65 / 0.51 | 0.74 / 0.65 / 0.43 |

## 5. Disclosure: the test split was executed twice by accident

The first launch of the test run (`test_1b6ae2d2`) was started in the background and I believed it had died, so I launched it again (`test_0d5035ce`); both were in fact running and overlapped, so **each prompt version was executed on the test split twice** instead of once. I report `test_0d5035ce` (the run whose output I read) as the pre-registered result and disclose the other in full. No prompt, rule or choice was changed between them or after seeing either result; selection had already been made on dev.

| run | version | predicted | exact micro F1 | lenient micro F1 |
|---|---|---|---|---|
| test_0d5035ce (reported) | v2 | 2101 | 0.433 | 0.569 |
| test_0d5035ce (reported) | v3 | 4081 | 0.485 | 0.633 |
| test_1b6ae2d2 (duplicate) | v2 | 2147 | 0.444 | 0.566 |
| test_1b6ae2d2 (duplicate) | v3 | 4081 | 0.485 | 0.633 |

The v3 result is identical in both runs (propagation absorbs the small run-to-run differences in what the model accepts); v2 differs by 0.011 exact micro F1 because the two launches raced each other for the same cache entries and produced slightly different model outputs. The headline (v3 exact micro F1 0.485) does not depend on which run is read.

## 6. Spend so far (CR-007, hard cap $20)

Dev ablation $0.0967 (78 real calls) + test runs $0.0582 and $0.0605 (the accidental duplicate) = **about $0.215**; everything else in STOP 1 and STOP 2 was $0 (diagnostics, scraper, propagation, replays).
