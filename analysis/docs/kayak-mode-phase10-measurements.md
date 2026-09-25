# Phase 10 measurements

Measured on the phase-9 pages and the phase-10 builds, using the same 200 seeded pairs per map (seed 20260923). Stay on paths is measured off and on. The exhaustive reference compares both objective labels, including launch edges, with tolerance `1e-8 + 1e-12 × max(|actual|, |reference|)`. Timings use Firefox 153.0 through Playwright 1.62.0. Every browser measurement restores the mode and goal way it borrowed.

Launch lengths below are measured in the source metric projection. Browser route lengths use the encoded coordinates, so a short tie can differ by millimetres. New access means that the road could not reach the same connected paddle water within 500 m along the old land network, including its inferred portages and excluding off-network connectors. Component membership is undirected; the 500 m measures land travel.

## Launches

| Map | Ties | Dead ends | Passing | New access within 500 m | Length min / median / p95 / max m | Total m |
|---|---:|---:|---:|---:|---:|---:|
| malingsbo-kloten | 2220 | 269 | 1951 | 808 | 0.059 / 12.514 / 27.792 / 29.997 | 30915.681 |
| abisko | 350 | 21 | 329 | 162 | 0.137 / 13.376 / 26.825 / 29.973 | 4915.738 |
| lomsdal-visten | 1825 | 404 | 1421 | 494 | 0.013 / 11.167 / 27.601 / 29.973 | 23232.458 |

The spacing sweep measures distance along the continuous bank, including closed rings. Dead ends are retained first; passing ties are ordered by gap and geometry. Existing road/shore junctions also occupy the bank. Candidate subdivision follows the chosen spacing, so these are catalogue counts, not nested subsets. All retained ties connect directly from a walking edge to the shore after noding; no inferred bridge is needed to complete a launch.

| Map | 50 m: ties / new access | 100 m: ties / new access | 200 m: ties / new access |
|---|---:|---:|---:|
| malingsbo-kloten | 3093 / 1100 | 2220 / 808 | 1572 / 575 |
| abisko | 491 / 214 | 350 / 162 | 235 / 117 |
| lomsdal-visten | 2549 / 673 | 1825 / 494 | 1304 / 366 |

Keep 100 m: compared with 50 m it removes 1738 ties (28.3%) and finds 73.7% as many new access points. Going to 200 m removes another 1284 ties and finds 406 fewer new access points (27.7%). This keeps short shore access without adding every nearby passing-road candidate.

| Map | Nodes before → after | Edges before → after | Launch edges |
|---|---:|---:|---:|
| malingsbo-kloten | 145558 → 148291 | 289548 → 294642 | 2282 |
| abisko | 48645 → 49101 | 105088 → 105923 | 360 |
| lomsdal-visten | 188541 → 190591 | 398191 → 402240 | 1884 |

## Seeded pairs

Here `kayak` and `walking` have Stay on paths off; `kayak-paths` and `paths` have it on. Carry and paddle are physical metres, not weighted land price. Ferry metres are separate. A changed answer differs by more than 0.01 m in length or source credit. Timings cover the production search, excluding the exhaustive reference; p95 uses linear interpolation over all 200 searches.

| Map / setting | Answers changed | Carry m before → after | Paddle m before → after | Ferry m before → after | p95 ms before → after | Reference |
|---|---:|---:|---:|---:|---:|---:|
| abisko / kayak | 64 / 200 | 365414.373 → 401840.335 | 1485367.608 → 1648977.793 | 0.000 → 0.000 | 239.60 → 347.30 | 200 / 200 |
| abisko / kayak-paths | 74 / 200 | 365414.373 → 483934.540 | 1485367.608 → 1613066.793 | 0.000 → 0.000 | 235.30 → 357.55 | 200 / 200 |
| malingsbo-kloten / kayak | 122 / 200 | 640761.545 → 727709.059 | 2553601.085 → 2595525.051 | 0.000 → 0.000 | 1637.55 → 2155.05 | 200 / 200 |
| malingsbo-kloten / kayak-paths | 131 / 200 | 640761.545 → 885961.503 | 2553601.085 → 2481108.561 | 0.000 → 0.000 | 1678.40 → 2015.00 | 200 / 200 |
| lomsdal-visten / kayak | 69 / 200 | 969576.054 → 1231570.310 | 1943859.778 → 2094114.784 | 703451.978 → 798000.017 | 2771.40 → 3474.50 | 200 / 200 |
| lomsdal-visten / kayak-paths | 77 / 200 | 969576.054 → 1539035.792 | 1943859.778 → 2158190.747 | 703451.978 → 878530.597 | 2872.35 → 3366.35 | 200 / 200 |

Walking whole-route lengths (including crossings):

| Map / setting | Answers changed | Whole length m before → after | p95 ms before → after | Reference |
|---|---:|---:|---:|---:|
| abisko / walking | 6 / 200 | 1605464.094 → 1605128.139 | 1547.95 → 1448.55 | 200 / 200 |
| abisko / paths | 10 / 200 | 1767071.617 → 1768193.703 | 747.75 → 797.00 | 200 / 200 |
| malingsbo-kloten / walking | 16 / 200 | 2192227.509 → 2191717.686 | 2575.70 → 2595.80 | 200 / 200 |
| malingsbo-kloten / paths | 22 / 200 | 2306304.989 → 2310381.326 | 1940.30 → 2110.25 | 200 / 200 |
| lomsdal-visten / walking | 15 / 200 | 3568788.293 → 3570106.239 | 10692.40 → 10599.30 | 200 / 200 |
| lomsdal-visten / paths | 14 / 200 | 3886125.001 → 3885465.553 | 3946.00 → 3859.50 | 200 / 200 |

## Largest kayak carry increases

The longer carries are expected under Uwe’s choice of paths. Pair indices identify the frozen seed sample; the before/after route records retain endpoints, source credits, connectors and both prices.

| Map / switch | Pair | Carry m before → after | Paddle m before → after | Carry increase m |
|---|---:|---:|---:|---:|
| malingsbo-kloten / off | 178 | 18346.057 → 22907.773 | 84713.776 → 68489.698 | 4561.716 |
| malingsbo-kloten / off | 193 | 9505.040 → 13877.244 | 4827.932 → 23671.784 | 4372.204 |
| malingsbo-kloten / off | 14 | 7163.100 → 11355.206 | 1053.973 → 891.739 | 4192.106 |
| malingsbo-kloten / on | 118 | 11853.378 → 20916.015 | 76100.719 → 77620.447 | 9062.637 |
| malingsbo-kloten / on | 138 | 9772.306 → 18823.597 | 64825.915 → 60959.828 | 9051.291 |
| malingsbo-kloten / on | 158 | 14582.920 → 22985.110 | 72200.676 → 75227.370 | 8402.190 |
| abisko / off | 78 | 10941.615 → 22006.904 | 29340.486 → 23546.324 | 11065.289 |
| abisko / off | 118 | 10939.627 → 17712.136 | 7996.912 → 1025.647 | 6772.509 |
| abisko / off | 158 | 4894.681 → 9929.033 | 15021.195 → 20546.911 | 5034.352 |
| abisko / on | 78 | 10941.615 → 23890.668 | 29340.486 → 23090.182 | 12949.052 |
| abisko / on | 118 | 10939.627 → 20153.480 | 7996.912 → 569.505 | 9213.853 |
| abisko / on | 175 | 3643.275 → 12213.697 | 2584.269 → 11291.714 | 8570.421 |
| lomsdal-visten / off | 159 | 31874.747 → 57254.249 | 1733.537 → 6906.964 | 25379.502 |
| lomsdal-visten / off | 58 | 42380.834 → 67463.864 | 29671.463 → 61068.606 | 25083.031 |
| lomsdal-visten / off | 139 | 24782.842 → 43472.172 | 524.619 → 1883.559 | 18689.330 |
| lomsdal-visten / on | 198 | 41946.522 → 78941.525 | 61603.749 → 78084.825 | 36995.003 |
| lomsdal-visten / on | 134 | 13215.489 → 46393.645 | 8428.254 → 5787.330 | 33178.156 |
| lomsdal-visten / on | 18 | 20252.582 → 50926.267 | 5168.583 → 6129.295 | 30673.684 |

## Largest whole-route increases

Water still has zero primary price: a lower land price can buy a much longer paddle. These are the largest increases in carry plus paddle plus ferry, separately from the carry increases above.

| Map / switch | Pair | Whole m before → after | Carry delta m | Paddle delta m | Ferry delta m |
|---|---:|---:|---:|---:|---:|
| malingsbo-kloten / off | 98 | 30634.808 → 85768.711 | 2135.739 | 52998.164 | 0.000 |
| malingsbo-kloten / off | 76 | 39537.747 → 67542.718 | 1550.305 | 26454.666 | 0.000 |
| malingsbo-kloten / off | 93 | 15943.409 → 41601.965 | 2744.761 | 22913.796 | 0.000 |
| malingsbo-kloten / on | 98 | 30634.808 → 98404.948 | 5801.178 | 61968.962 | 0.000 |
| malingsbo-kloten / on | 76 | 39537.747 → 67724.129 | 1888.059 | 26298.323 | 0.000 |
| malingsbo-kloten / on | 75 | 4888.830 → 31233.226 | 4739.949 | 21604.446 | 0.000 |
| abisko / off | 14 | 7551.359 → 67049.665 | 4497.981 | 55000.325 | 0.000 |
| abisko / off | 199 | 21600.679 → 77244.207 | -3572.495 | 59216.023 | 0.000 |
| abisko / off | 18 | 20134.352 → 61779.822 | -618.304 | 42263.774 | 0.000 |
| abisko / on | 14 | 7551.359 → 67057.776 | 4556.503 | 54949.913 | 0.000 |
| abisko / on | 199 | 21600.679 → 67658.093 | 229.468 | 45827.946 | 0.000 |
| abisko / on | 18 | 20134.352 → 61771.158 | -626.968 | 42263.774 | 0.000 |
| lomsdal-visten / off | 58 | 72052.296 → 154495.360 | 25083.031 | 31397.144 | 25962.889 |
| lomsdal-visten / off | 99 | 45757.125 → 86730.157 | 9647.848 | 6011.338 | 25313.846 |
| lomsdal-visten / off | 97 | 45706.002 → 81229.748 | 8299.292 | 27224.454 | 0.000 |
| lomsdal-visten / on | 58 | 72052.296 → 156835.083 | 28933.625 | 29886.272 | 25962.889 |
| lomsdal-visten / on | 198 | 123372.869 → 183703.450 | 36995.003 | 16481.076 | 6854.501 |
| lomsdal-visten / on | 135 | 5605.158 → 65859.777 | 9251.138 | 24643.670 | 26359.811 |

## Walking pair changes

The prices are unchanged. New road junctions offer additional entries and snaps. This distribution has no stop gate; recorded readings below retain the old-way price comparison.

| Map / switch | Length delta min / p05 / median / p95 / max m | Longer / shorter |
|---|---:|---:|
| malingsbo-kloten / off | -437.888 / 0.000 / 0.000 / 0.007 / 124.832 | 10 / 6 |
| malingsbo-kloten / on | -459.972 / 0.000 / 0.000 / 6.579 / 3173.152 | 16 / 6 |
| abisko / off | -344.309 / 0.000 / 0.000 / 0.001 / 258.248 | 2 / 4 |
| abisko / on | -680.042 / 0.000 / 0.000 / 0.001 / 995.337 | 6 / 4 |
| lomsdal-visten / off | -1218.528 / 0.000 / 0.000 / 0.015 / 1248.167 | 12 / 3 |
| lomsdal-visten / on | -485.017 / 0.000 / 0.000 / 0.009 / 133.750 | 10 / 4 |

## Fixed reader legs

Public figures below include the profile’s finer shore split. They can differ from the search’s water-grid split. The phase-2 sweep, Kloten reconstructed starts, phone-2 and Korslångssmedja use the investigation’s fixed inputs. Every recorded route whose metre figure changes at three decimals is listed below, including millimetre-scale geometry changes. Old fixed-network prices retain the unchanged factors; old connectors are sampled on the new graph before comparing price.

malingsbo-kloten

| Leg / Stay on paths | Public carry / paddle m before | After |
|---|---:|---:|
| kayak_shore / off | 0.000 / 831.576 | 0.000 / 831.576 |
| kayak_bay / off | 0.000 / 1073.404 | 0.000 / 1073.404 |
| kayak_portage / off | 46.348 / 619.511 | 46.348 / 619.511 |
| recorded_walking_shore / off | 5.025 / 1904.659 | 5.025 / 1904.659 |
| accepted_dammtjarn / off | 266.191 / 90.404 | 266.191 / 90.404 |
| accepted_helper / off | 5892.463 / 24316.168 | 5016.549 / 25436.036 |
| accepted_noding_example / off | 55.990 / 0.000 | 67.944 / 13.114 |
| korslangssmedja / off | 0.000 / 4419.018 | 0.000 / 4419.018 |
| phone_near_59_946_15_259 / off | 15.083 / 126.625 | 15.083 / 126.625 |
| phase2_bay / off | 0.000 / 1073.404 | 0.000 / 1073.404 |
| phase2_lake / off | 0.000 / 1740.551 | 0.000 / 1740.551 |
| phase2_portage / off | 560.819 / 1952.227 | 802.336 / 1677.396 |
| kloten_north / off | 231.408 / 0.000 | 224.873 / 28.514 |
| kloten_proxy / off | 411.031 / 7088.969 | 224.873 / 6898.232 |
| kloten_offroad / off | 202.687 / 6914.266 | 302.427 / 7189.968 |
| phone2_12 / off | 173.877 / 0.000 | 175.289 / 0.000 |
| phone2_23 / off | 40.567 / 2.704 | 49.584 / 0.000 |
| kayak_shore / on | 0.000 / 831.576 | 0.000 / 831.576 |
| kayak_bay / on | 0.000 / 1073.404 | 0.000 / 1073.404 |
| kayak_portage / on | 46.348 / 619.511 | 46.348 / 619.511 |
| recorded_walking_shore / on | 5.025 / 1904.659 | 5.025 / 1904.659 |
| accepted_dammtjarn / on | 266.191 / 90.404 | 977.311 / 702.419 |
| accepted_helper / on | 5892.463 / 24316.168 | 5454.715 / 25269.846 |
| accepted_noding_example / on | 55.990 / 0.000 | 67.944 / 13.114 |
| korslangssmedja / on | 0.000 / 4419.018 | 0.000 / 4419.018 |
| phone_near_59_946_15_259 / on | 15.083 / 126.625 | 15.083 / 126.625 |
| phase2_bay / on | 0.000 / 1073.404 | 0.000 / 1073.404 |
| phase2_lake / on | 0.000 / 1740.551 | 0.000 / 1740.551 |
| phase2_portage / on | 560.819 / 1952.227 | 1050.455 / 849.848 |
| kloten_north / on | 231.408 / 0.000 | 224.873 / 28.514 |
| kloten_proxy / on | 411.031 / 7088.969 | 224.873 / 6898.232 |
| kloten_offroad / on | 202.687 / 6914.266 | 302.427 / 7189.968 |
| phone2_12 / on | 173.877 / 0.000 | 175.289 / 0.000 |
| phone2_23 / on | 40.567 / 2.704 | 49.584 / 0.000 |

abisko

| Leg / Stay on paths | Public carry / paddle m before | After |
|---|---:|---:|
| kayak_shore / off | 0.000 / 2167.118 | 0.000 / 2167.118 |
| kayak_bay / off | 0.000 / 1416.986 | 0.000 / 1416.986 |
| kayak_portage / off | 1.450 / 417.749 | 1.450 / 417.749 |
| kayak_shore / on | 0.000 / 2167.118 | 0.000 / 2167.118 |
| kayak_bay / on | 0.000 / 1416.986 | 0.000 / 1416.986 |
| kayak_portage / on | 1.450 / 417.749 | 1.450 / 417.749 |

lomsdal-visten

| Leg / Stay on paths | Public carry / paddle m before | After |
|---|---:|---:|
| kayak_shore / off | 0.000 / 938.729 | 0.000 / 938.729 |
| kayak_bay / off | 0.000 / 699.661 | 0.000 / 699.661 |
| kayak_portage / off | 454.048 / 1788.717 | 144.679 / 1550.194 |
| accepted_typed_leg / off | 248.756 / 829.756 | 249.461 / 829.756 |
| kayak_shore / on | 0.000 / 938.729 | 0.000 / 938.729 |
| kayak_bay / on | 0.000 / 699.661 | 0.000 / 699.661 |
| kayak_portage / on | 454.048 / 1788.717 | 687.770 / 403.335 |
| accepted_typed_leg / on | 248.756 / 829.756 | 249.461 / 829.756 |

Moved recorded walking ways

Whole lengths are listed for the frozen route inputs; public reader legs show foot / water / straight-ground metres. A movement changes the value rounded to three decimals.

| Map / reading / paths | Metres before → after | Price of old way → new | Reason |
|---|---:|---:|---|
| malingsbo-kloten / the_way_to_the_next_goal [3] / off | 12277.004 → 12277.005 | 15900.386095 → 15900.387021 | noding changes the measured geometry or snap |
| malingsbo-kloten / the_way_to_the_next_goal [4] / off | 12076.156 → 12076.158 | 15512.271675 → 15512.274733 | noding changes the measured geometry or snap |
| malingsbo-kloten / a_way_counts_foot_and_water [5] / off | 22734.606 → 22734.613 | 28974.766669 → 28974.775649 | noding changes the measured geometry or snap |
| malingsbo-kloten / a_way_counts_foot_and_water [6] / off | 12670.820 → 12670.825 | 17399.699362 → 17399.705552 | noding changes the measured geometry or snap |
| malingsbo-kloten / a_way_counts_foot_and_water [7] / off | 10843.785 → 10843.787 | 15231.313903 → 15231.316692 | noding changes the measured geometry or snap |
| malingsbo-kloten / a_dry_way_keeps_its_words [8] / off | 12392.231 → 12392.236 | 15905.807765 → 15905.813955 | noding changes the measured geometry or snap |
| malingsbo-kloten / a_dry_way_keeps_its_words [9] / off | 10565.196 → 10565.198 | 13737.422306 → 13737.425095 | noding changes the measured geometry or snap |
| malingsbo-kloten / the_walking_modes_never_take_the_water [10] / off | 3274.297 → 3274.298 | 3730.891919 → 3730.892042 | noding changes the measured geometry or snap |
| malingsbo-kloten / a_goal_the_reader_sets [11] / off | 22796.111 → 22796.118 | 29054.723428 → 29054.732407 | noding changes the measured geometry or snap |
| malingsbo-kloten / a_goal_the_reader_sets [12] / off | 12500.927 → 12500.931 | 15857.714351 → 15857.720541 | noding changes the measured geometry or snap |
| malingsbo-kloten / a_goal_the_reader_sets [13] / off | 10521.510 → 10521.512 | 13491.232437 → 13491.235226 | noding changes the measured geometry or snap |
| malingsbo-kloten / a_goal_the_reader_sets [14] / off | 9526.787 → 9526.789 | 12387.057173 → 12387.059757 | noding changes the measured geometry or snap |
| malingsbo-kloten / a_goal_the_reader_sets [15] / off | 13491.634 → 13491.639 | 17334.598721 → 17334.605116 | noding changes the measured geometry or snap |
| malingsbo-kloten / a_goal_the_reader_sets [16] / off | 9284.155 → 9284.159 | 12359.195295 → 12359.200768 | noding changes the measured geometry or snap |
| malingsbo-kloten / a_goal_the_reader_sets [17] / off | 14116.006 → 13926.600 | 18546.797943 → 18544.121349 | new entry node, cheaper by the unchanged rule |
| malingsbo-kloten / a_goal_the_reader_sets [18] / off | 8581.574 → 8392.166 | 11681.113459 → 11678.434323 | new entry node, cheaper by the unchanged rule |
| malingsbo-kloten / a_goal_the_reader_sets [19] / off | 8063.495 → 8063.497 | 11189.737952 → 11189.740393 | noding changes the measured geometry or snap |
| malingsbo-kloten / a_goal_the_reader_sets [20] / off | 17261.679 → 17261.684 | 22189.038943 → 22189.045382 | noding changes the measured geometry or snap |
| malingsbo-kloten / a_goal_the_reader_sets [21] / off | 8581.574 → 8392.166 | 11681.113459 → 11678.434323 | new entry node, cheaper by the unchanged rule |
| malingsbo-kloten / a_goal_the_reader_sets [22] / off | 14146.855 → 13957.449 | 19714.673998 → 19711.997403 | new entry node, cheaper by the unchanged rule |
| malingsbo-kloten / a_goal_the_reader_sets [23] / off | 22826.960 → 22826.967 | 30222.599482 → 30222.608462 | noding changes the measured geometry or snap |
| malingsbo-kloten / a_goal_the_reader_sets [24] / off | 25689.480 → 25689.482 | 31851.448975 → 31851.451501 | noding changes the measured geometry or snap |
| malingsbo-kloten / a_goal_the_reader_sets [25] / off | 46322.527 → 46322.528 | 57603.165599 → 57603.166744 | noding changes the measured geometry or snap |
| malingsbo-kloten / a_goal_the_reader_sets [26] / off | 46342.015 → 46342.016 | 57661.629133 → 57661.630278 | noding changes the measured geometry or snap |
| malingsbo-kloten / a_goal_the_reader_sets [27] / off | 25187.088 → 25187.095 | 33487.569131 → 33487.578110 | noding changes the measured geometry or snap |
| malingsbo-kloten / a_goal_the_reader_sets [29] / off | 22795.741 → 22795.748 | 29054.241911 → 29054.250891 | noding changes the measured geometry or snap |
| malingsbo-kloten / a_goal_the_reader_sets [30] / off | 115287.739 → 115287.740 | 307046.164517 → 307046.166162 | noding changes the measured geometry or snap |
| malingsbo-kloten / a_goal_the_reader_sets [31] / off | 117605.240 → 117605.241 | 311350.494448 → 311350.496361 | noding changes the measured geometry or snap |
| malingsbo-kloten / a_goal_the_reader_sets [33] / off | 38046.576 → 38046.577 | 46762.766557 → 46762.767759 | noding changes the measured geometry or snap |
| malingsbo-kloten / a_tap_that_could_have_meant_several_lines [38] / off | 12907.603 → 12907.604 | 16533.433698 → 16533.435065 | noding changes the measured geometry or snap |
| malingsbo-kloten / a_route_read_after_planning [39] / off | 13355.588 → 13355.589 | 17302.544669 → 17302.545842 | noding changes the measured geometry or snap |
| malingsbo-kloten / a_route_read_after_planning [40] / off | 12157.169 → 12157.171 | 15431.522397 → 15431.525207 | noding changes the measured geometry or snap |
| malingsbo-kloten / the_way_to_the_next_goal [3] / on | 12277.004 → 12277.005 | 15900.386095 → 15900.387021 | noding changes the measured geometry or snap |
| malingsbo-kloten / the_way_to_the_next_goal [4] / on | 12076.156 → 12076.158 | 15512.271675 → 15512.274733 | noding changes the measured geometry or snap |
| malingsbo-kloten / a_way_counts_foot_and_water [5] / on | 22734.606 → 22734.613 | 28974.766669 → 28974.775649 | noding changes the measured geometry or snap |
| malingsbo-kloten / a_way_counts_foot_and_water [6] / on | 12670.820 → 12670.825 | 19959.071979 → 19959.078169 | noding changes the measured geometry or snap |
| malingsbo-kloten / a_way_counts_foot_and_water [7] / on | 10843.785 → 10843.787 | 17790.686520 → 17790.689309 | noding changes the measured geometry or snap |
| malingsbo-kloten / a_dry_way_keeps_its_words [8] / on | 12392.231 → 12392.236 | 16685.681733 → 16685.687923 | noding changes the measured geometry or snap |
| malingsbo-kloten / a_dry_way_keeps_its_words [9] / on | 10565.196 → 10565.198 | 14517.296274 → 14517.299063 | noding changes the measured geometry or snap |
| malingsbo-kloten / the_walking_modes_never_take_the_water [10] / on | 3274.297 → 3274.298 | 4283.210182 → 4283.210305 | noding changes the measured geometry or snap |
| malingsbo-kloten / a_goal_the_reader_sets [11] / on | 22796.111 → 22796.118 | 29054.723428 → 29054.732407 | noding changes the measured geometry or snap |
| malingsbo-kloten / a_goal_the_reader_sets [12] / on | 12500.927 → 12500.931 | 15857.714351 → 15857.720541 | noding changes the measured geometry or snap |
| malingsbo-kloten / a_goal_the_reader_sets [13] / on | 10521.510 → 10521.512 | 13491.232437 → 13491.235226 | noding changes the measured geometry or snap |
| malingsbo-kloten / a_goal_the_reader_sets [14] / on | 9526.787 → 9526.789 | 13165.145050 → 13165.147634 | noding changes the measured geometry or snap |
| malingsbo-kloten / a_goal_the_reader_sets [15] / on | 13491.634 → 13491.639 | 18112.686598 → 18112.692993 | noding changes the measured geometry or snap |
| malingsbo-kloten / a_goal_the_reader_sets [16] / on | 9669.080 → 9669.084 | 13818.144879 → 13818.150352 | noding changes the measured geometry or snap |
| malingsbo-kloten / a_goal_the_reader_sets [17] / on | 14194.737 → 14194.740 | 19908.258903 → 19908.262410 | noding changes the measured geometry or snap |
| malingsbo-kloten / a_goal_the_reader_sets [18] / on | 8660.305 → 8660.306 | 14071.874852 → 14071.875817 | noding changes the measured geometry or snap |
| malingsbo-kloten / a_goal_the_reader_sets [19] / on | 9348.893 → 9348.895 | 13138.477666 → 13138.480207 | noding changes the measured geometry or snap |
| malingsbo-kloten / a_goal_the_reader_sets [20] / on | 17261.679 → 17261.684 | 23218.339376 → 23218.345815 | noding changes the measured geometry or snap |
| malingsbo-kloten / a_goal_the_reader_sets [21] / on | 8660.305 → 8660.306 | 14071.874852 → 14071.875817 | noding changes the measured geometry or snap |
| malingsbo-kloten / a_goal_the_reader_sets [22] / on | 15116.719 → 15116.722 | 23403.426966 → 23403.430473 | noding changes the measured geometry or snap |
| malingsbo-kloten / a_goal_the_reader_sets [23] / on | 23718.093 → 23718.100 | 32549.891491 → 32549.900470 | noding changes the measured geometry or snap |
| malingsbo-kloten / a_goal_the_reader_sets [24] / on | 26910.118 → 26910.120 | 37375.988757 → 37375.991283 | noding changes the measured geometry or snap |
| malingsbo-kloten / a_goal_the_reader_sets [25] / on | 46322.527 → 46322.528 | 57821.444291 → 57821.445436 | noding changes the measured geometry or snap |
| malingsbo-kloten / a_goal_the_reader_sets [26] / on | 46342.015 → 46342.016 | 58016.322738 → 58016.323883 | noding changes the measured geometry or snap |
| malingsbo-kloten / a_goal_the_reader_sets [27] / on | 28910.397 → 28783.827 | 38846.213276 → 38367.462709 | new entry node, cheaper by the unchanged rule |
| malingsbo-kloten / a_goal_the_reader_sets [29] / on | 22795.741 → 22795.748 | 29054.241911 → 29054.250891 | noding changes the measured geometry or snap |
| malingsbo-kloten / a_goal_the_reader_sets [30] / on | 116571.956 → 116571.957 | 955371.200455 → 955371.202052 | noding changes the measured geometry or snap |
| malingsbo-kloten / a_goal_the_reader_sets [31] / on | 121815.128 → 121688.552 | 964030.242776 → 963551.484826 | new entry node, cheaper by the unchanged rule |
| malingsbo-kloten / a_goal_the_reader_sets [33] / on | 38046.576 → 38046.577 | 46981.045249 → 46981.046451 | noding changes the measured geometry or snap |
| malingsbo-kloten / a_tap_that_could_have_meant_several_lines [38] / on | 12907.603 → 12907.604 | 16533.433698 → 16533.435065 | noding changes the measured geometry or snap |
| malingsbo-kloten / a_route_read_after_planning [39] / on | 13355.588 → 13355.589 | 17302.544669 → 17302.545842 | noding changes the measured geometry or snap |
| malingsbo-kloten / a_route_read_after_planning [40] / on | 12157.169 → 12157.171 | 15431.522397 → 15431.525207 | noding changes the measured geometry or snap |
| malingsbo-kloten / kayak_shore / off | 686.232 / 37.565 / 686.232 → 716.449 / 41.746 / 266.031 | 2804.446668 → 2364.960373 | new entry node, cheaper by the unchanged rule |
| malingsbo-kloten / accepted_helper / off | 9284.155 / 0.000 / 387.876 → 9284.159 / 0.000 / 387.876 | 12359.195295 → 12359.200768 | noding changes the measured geometry or snap |
| malingsbo-kloten / accepted_noding_example / off | 55.990 / 0.000 / 55.990 → 68.399 / 0.000 / 25.221 | 167.970298 → 131.793807 | new entry node, cheaper by the unchanged rule |
| malingsbo-kloten / kayak_shore / on | 1067.730 / 36.760 / 343.600 → 716.449 / 41.746 / 266.031 | 5355.986149 → 4297.452649 | new entry node, cheaper by the unchanged rule |
| malingsbo-kloten / accepted_helper / on | 9669.080 / 0.000 / 192.638 → 9669.084 / 0.000 / 192.638 | 13818.144879 → 13818.150352 | noding changes the measured geometry or snap |
| malingsbo-kloten / accepted_noding_example / on | 55.990 / 0.000 / 55.990 → 68.399 / 0.000 / 25.221 | 559.900994 → 308.338350 | new entry node, cheaper by the unchanged rule |
| malingsbo-kloten / phone2_23 / on | 40.567 / 2.704 / 40.567 → 46.381 / 3.203 / 3.203 | 432.715161 → 248.302020 | new entry node, cheaper by the unchanged rule |
| abisko / a_goal_the_reader_sets [10] / off | 10581.373 → 10581.374 | 11981.854492 → 11981.854722 | noding changes the measured geometry or snap |
| abisko / a_goal_the_reader_sets [16] / off | 8516.793 → 8516.794 | 10526.763489 → 10526.764505 | noding changes the measured geometry or snap |
| abisko / a_goal_the_reader_sets [18] / off | 8516.793 → 8516.794 | 10526.763489 → 10526.764505 | noding changes the measured geometry or snap |
| abisko / a_goal_the_reader_sets [25] / off | 125823.010 → 125823.011 | 305275.838577 → 305275.838771 | noding changes the measured geometry or snap |
| abisko / a_goal_the_reader_sets [26] / off | 16836.257 → 16836.258 | 17799.998502 → 17799.998926 | noding changes the measured geometry or snap |
| abisko / a_goal_the_reader_sets [28] / off | 113944.708 → 114019.624 | 294608.317202 → 294589.880773 | new entry node, cheaper by the unchanged rule |
| abisko / a_tap_in_the_middle_of_a_long_edge [39] / off | 3907.930 → 3907.931 | 4298.723166 → 4298.723615 | noding changes the measured geometry or snap |
| abisko / a_tap_in_the_middle_of_a_long_edge [42] / off | 5861.768 → 5861.769 | 6447.944954 → 6447.945404 | noding changes the measured geometry or snap |
| abisko / a_goal_the_reader_sets [11] / on | 9715.083 → 9715.084 | 15058.199491 → 15058.199721 | noding changes the measured geometry or snap |
| abisko / a_goal_the_reader_sets [12] / on | 8321.650 → 8321.651 | 12216.273583 → 12216.273777 | noding changes the measured geometry or snap |
| abisko / a_goal_the_reader_sets [16] / on | 8548.932 → 8548.933 | 16746.723023 → 16746.724039 | noding changes the measured geometry or snap |
| abisko / a_goal_the_reader_sets [18] / on | 8548.932 → 8548.933 | 16746.723023 → 16746.724039 | noding changes the measured geometry or snap |
| abisko / a_goal_the_reader_sets [25] / on | 134581.812 → 134581.813 | 909428.596288 → 909428.596482 | noding changes the measured geometry or snap |
| abisko / a_goal_the_reader_sets [26] / on | 16836.257 → 16836.258 | 17799.998502 → 17799.998926 | noding changes the measured geometry or snap |
| abisko / a_goal_the_reader_sets [27] / on | 121200.765 → 121200.766 | 894140.654624 → 894140.656252 | noding changes the measured geometry or snap |
| abisko / a_tap_beside_a_path_in_plan_mode [36] / on | 2248.588 → 2248.589 | 3504.711701 → 3504.711751 | noding changes the measured geometry or snap |
| abisko / a_tap_in_the_middle_of_a_long_edge [39] / on | 3907.930 → 3907.931 | 4298.723166 → 4298.723615 | noding changes the measured geometry or snap |
| abisko / a_tap_in_the_middle_of_a_long_edge [42] / on | 5861.768 → 5861.769 | 6447.944954 → 6447.945404 | noding changes the measured geometry or snap |
| lomsdal-visten / a_way_to_a_goal_becomes_a_plan [1] / off | 2579.392 → 2575.664 | 7713.398235 → 7709.670362 | new entry node, cheaper by the unchanged rule |
| lomsdal-visten / a_way_counts_foot_and_water [5] / off | 3215.452 → 3215.454 | 16970.613043 → 16970.614746 | noding changes the measured geometry or snap |
| lomsdal-visten / a_goal_the_reader_sets [22] / off | 36650.950 → 36650.965 | 45252.526619 → 45252.545757 | noding changes the measured geometry or snap |
| lomsdal-visten / a_goal_the_reader_sets [23] / off | 36669.793 → 36669.808 | 45309.055777 → 45309.074915 | noding changes the measured geometry or snap |
| lomsdal-visten / a_goal_the_reader_sets [25] / off | 140423.653 → 140423.667 | 287546.175483 → 287546.194621 | noding changes the measured geometry or snap |
| lomsdal-visten / a_goal_the_reader_sets [28] / off | 124792.383 → 124792.384 | 263593.427966 → 263593.429075 | noding changes the measured geometry or snap |
| lomsdal-visten / a_goal_the_reader_sets [30] / off | 45855.469 → 45855.484 | 57936.608978 → 57936.628339 | noding changes the measured geometry or snap |
| lomsdal-visten / a_way_across_a_sound_goes_round_by_land [31] / off | 3218.856 → 3218.858 | 16724.300547 → 16724.302250 | noding changes the measured geometry or snap |
| lomsdal-visten / a_way_across_a_sound_goes_round_by_land [32] / off | 12882.792 → 12882.793 | 32181.213117 → 32181.214789 | noding changes the measured geometry or snap |
| lomsdal-visten / a_route_read_after_planning [43] / off | 12475.413 → 12470.477 | 12475.413019 → 12470.476684 | new entry node, cheaper by the unchanged rule |
| lomsdal-visten / a_route_read_after_planning [44] / off | 12962.206 → 12950.344 | 12962.283714 → 12950.343956 | new entry node, cheaper by the unchanged rule |
| lomsdal-visten / a_way_counts_foot_and_water [5] / on | 3215.452 → 3215.454 | 22536.715981 → 22536.717684 | noding changes the measured geometry or snap |
| lomsdal-visten / a_goal_the_reader_sets [22] / on | 36650.950 → 36650.965 | 45266.874123 → 45266.893261 | noding changes the measured geometry or snap |
| lomsdal-visten / a_goal_the_reader_sets [23] / on | 36669.793 → 36669.808 | 45455.304650 → 45455.323788 | noding changes the measured geometry or snap |
| lomsdal-visten / a_goal_the_reader_sets [25] / on | 145756.521 → 145756.536 | 734688.972792 → 734688.991941 | noding changes the measured geometry or snap |
| lomsdal-visten / a_goal_the_reader_sets [28] / on | 125532.485 → 125532.486 | 707750.703149 → 707750.704265 | noding changes the measured geometry or snap |
| lomsdal-visten / a_goal_the_reader_sets [30] / on | 45855.469 → 45855.484 | 57950.956481 → 57950.975843 | noding changes the measured geometry or snap |
| lomsdal-visten / a_way_across_a_sound_goes_round_by_land [31] / on | 3218.856 → 3218.858 | 21257.954335 → 21257.956038 | noding changes the measured geometry or snap |
| lomsdal-visten / a_way_across_a_sound_goes_round_by_land [32] / on | 12882.792 → 12882.793 | 57519.029614 → 57519.031286 | noding changes the measured geometry or snap |
| lomsdal-visten / a_route_read_after_planning [43] / on | 12475.413 → 12470.477 | 12475.413019 → 12470.476684 | new entry node, cheaper by the unchanged rule |
| lomsdal-visten / a_route_read_after_planning [44] / on | 12962.206 → 12950.344 | 12962.283714 → 12950.343956 | new entry node, cheaper by the unchanged rule |
| lomsdal-visten / kayak_bay / off | 2659.009 / 67.753 / 637.278 → 2678.642 / 12.553 / 752.997 | 6683.544982 → 5460.913106 | new entry node, cheaper by the unchanged rule |
| lomsdal-visten / kayak_bay / on | 2659.009 / 67.753 / 637.278 → 2678.642 / 12.553 / 752.997 | 11115.745039 → 10648.415966 | new entry node, cheaper by the unchanged rule |

## Kloten launch and the switch

The short landing is a **passing-road launch**, not a degree-1 road end.
Catalogue tie 645 joins walking node **141123** to shore node **94456**.
The road foot is **(59.89787673407344, 15.288431474887135)**, **6.085713 m**
from unsimplified source water; the tie to the paddle shore is **6.413967 m**
in EPSG:3006, **6.405672 m** in the encoded browser graph. Its shore end is
**(59.8978909474998, 15.2883203825611)**. Both phone-2's 2→3 and the
reconstructed Kloten P1→northern-shore way use this tie in both switch settings.
This resolves the earlier existing-node landing stop under Uwe's permission
to split the road. The superseded existing-node experiment lost this original
short landing; its farther alternative and the old stop remain in the record.

Phone-2's 1→2 follows **175.289 m of road**, with no straight ground, in both
settings. Its 2→3 is **43.178 m road + 6.406 m launch**, with no paddle needed
before the endpoint. P1→northern shore is **224.873 m carry + 28.514 m paddle**;
P1→P2 proxy keeps that launch and carries **224.873 m** before paddling
**6,898.232 m**. The off-road start carries **302.427 m** and paddles
**7,189.968 m**. These are the public profile splits, in either setting.

The measured switch-sensitive input is **(59.8967, 15.2889) →
(59.898026273, 15.288010427)**, near the same landing:

| Stay on paths | Carry m | Straight ground m | Road m | Launch m | Paddle m |
|---|---:|---:|---:|---:|---:|
| Off | 147.612 | 88.881 | 52.325 | 6.406 | 28.514 |
| On | 321.419 | 14.913 | 300.100 | 6.406 | 28.514 |

The switch buys a longer road carry to avoid ground, exactly as Uwe chose.
It remains visible in kayak mode. The drive names both settings and restores
mode, goal way, plan and undo history after borrowing them.

At the original walking-example taps, the built answer is **68.399 m**:
**25.221 m ground + 43.178 m road**, using no launch. Its re-priced old way
costs **167.970 → 131.794** with the switch off and **559.901 → 308.338**
with it on. The original **55.990 → 68.341 m** diagnostic remains the case
Uwe was shown; this is the measurement on the final graph.

## Compact panel

While planning a kayak way, the compact figure gives the complete distance,
then water and foot in the heading's form: `7.50 km · 7.10 km 🛶 · 0.40 km 🚶`.
The point count and ascent yield this space to the requested split. The full
figure wraps between distance chunks on a phone; each number keeps its glyph.
At the measured 390 × 844 viewport, the Kloten pilot used **194 of 194 px**,
with a **32 px** two-line name inside the unchanged **42 px** header. Working
and profile-crosshair readings retain their own text. Walking keeps its plain
point-count, distance and ascent line.

The final Malingsbo-Kloten panel rebuild was compared with the page used for
its 800 route comparisons: encoded graph header, payload and routing code are
byte-identical. The UI rebuild therefore preserves those search timings and
differential results. Hashes are retained in `panel-routing-proof.json`.

## Full-suite scene figures

The dry-goal figures changed only in their sample count after launch noding and
resampling. Removing that count makes each old/new figure HTML byte-identical;
all three GPX description hashes remain identical. Distances below show the
sub-centimetre geometry differences, not a new walking price.

| Map | Walking m, before → after | Profile points, before → after |
|---|---:|---:|
| malingsbo-kloten | 22957.427001 → 22957.433909 | 9,074 → 9,051 |
| abisko | 16700.516927 → 16700.517343 | 6,418 → 6,412 |
| lomsdal-visten | 19101.256821 → 19101.256874 | 7,640 → 7,641 |

Malingsbo-Kloten's partial-edge tap fixture follows the same Topografi 50 road
from **59.883874 N, 15.740213 E**. The old edge number 67026 now names a different
edge. The road is **edge 67986**, shortened by launch noding from **3,439 to
3,436 m**; its half and three-quarter taps still test partial-edge routing.
The 400 m eligibility gate and routing checks are unchanged.

Other observed scene figures are below, including those within the existing
suite tolerances. These are layout, water-width and persisted-plan-size
readings; they are not claims that walking prices changed. Their tolerances
are unchanged. The moved kayak scene split is reported with both settings above.

| Map | Reading | Before → after |
|---|---|---:|
| malingsbo-kloten | what it weighs | 652 → 647 |
| abisko | what it weighs | 465 → 464 |
| lomsdal-visten | desktop: map free with nothing asked for | 96 → 97.8 |
| lomsdal-visten | upright: map free with nothing asked for | 96 → 98 |
| lomsdal-visten | sideways: map free with nothing asked for | 96 → 97.8 |
| lomsdal-visten | m shown by a quarter-width drag | 11188 → 11202 |
| lomsdal-visten | sideways: px the panel is | 186 → 189 |
| lomsdal-visten | px of map left above it | 565 → 562 |
| lomsdal-visten | and what width it says | 30 → 27 |
| lomsdal-visten | what it weighs | 549 → 540 |

The first full-suite attempt exposed a measurement-harness problem: Playwright
request interception prevented the offline worker's cold-tile check from
settling. An isolated Abisko A/B reproduced the timeout with interception and
passed all 31 readings with a refused external proxy instead. The latter lets
service-worker traffic use the normal browser path while keeping external
fetches blocked. No application change was made for that failure. The next
full suite exposed the figure hashes and stale edge number above; its routing
and UI invariants all passed. Both attempts are retained in scratch.

## Validation

The selected drive runs are green twice per page: **310 readings** on
Malingsbo-Kloten, **210** on Abisko and **214** on Lomsdal-Visten per run.
There are no broken invariants, moved figures or unrecorded figures. The
northern pages retain three declared scene skips for the Kloten road/switch
fixtures and the level-channel fixture. The selection includes all kayak
checks, the new readings, the dry-goal figure and the partial-edge tap.

The complete `command make drive-all` run is green: **1,708 / 1,634 / 1,641
readings** on Malingsbo-Kloten / Abisko / Lomsdal-Visten, **4,983** in all.
No invariant breaks, moved figures, unrecorded figures or undeclared skips
remain. The maps have 4 / 3 / 3 declared scene skips. The full run includes
the offline-worker checks as well as the new kayak readings.

`command make hooks-run` is green with network access: ruff format/check,
mypy (108 source files), both pytest suites and the standard hooks. Its first
run found four type errors: pandas' geometry-series indexing confused the
stubs, and an array/scalar nearest-result variable was reused. Selecting from
the same geometry arrays and naming the scalar separately resolves them
without changing geometry or prices. The first test session reached cleanup
without a failed test, then the scratch guard misresolved a directory-relative
`.cache` removal against the checkout. Honouring the directory file descriptor
fixed that guard; the complete hooks rerun passed. Shared inputs stayed read-only.

## Evidence

Scratch is `~/mockups/kayak-mode/phase10/`: `final/<map>/launch-audit.json`, the four `*-pairs.jsonl` files and four `*-readers.json` files per map, `recorded-walking.jsonl`, `pair-summary.json`, `switch-candidates.json` and `switch-public.json`. Frozen phase-9 pages and pair results are under `baseline-pages/` and `baseline/`. `measure.py` / `measure.js` / `reference.js`, `launch_audit.py` and `recorded_walking.py` reproduce the comparisons; each graph-loading process caps its address space at 8 GiB. `drive-<map>-1.log` / `-2.log`, `drive-all-<map>.log`, `drive-all-exit.json`, `hooks.log` and `hooks-exit.json` retain final validation; prior failed harness and snapshot runs are archived beside them.
