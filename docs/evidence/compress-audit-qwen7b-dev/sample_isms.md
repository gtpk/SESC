# Sample LLM ISMs (first 2 docs) — captured from compress-audit

## syn_dev_000000  (rule_coverage 0.67, self_containment 0.67, relations_structure 0.8)
[DICTIONARY]
Z1 := case_1824.marker_a = high and case_1824.marker_b = low
Z2 := case_1824.marker_a = low or case_1824.marker_b = high
Z3 := at least 2 of (case_1824.marker_a = high; case_1824.marker_b = high; case_1824.repair_score >= 0.5)
Z4 := case_1824.event_a occurs before case_1824.event_b
Z5 := case_1824.repair_score >= 0.8
Z6 := case_1824.marker_a = high and case_1824.marker_b = high

[RELATIONS]
Z1 Z2 !Z6
Z5 !Z2
Z6 !Z2
Z3 Z1 Z2 !Z6
Z4 Z1

NOTE: definitions encode CONDITIONS but DROP the conclusions (risk = HIGH/MEDIUM/LOW).

## syn_dev_000001  (rule_coverage 0.67, self_containment 0.67, relations_structure 1.0)
[DICTIONARY]
Z1 := case_2286.marker_a = high and case_2286.marker_b = low
... (same atomic conditions) ...

[RELATIONS]
Z1 !Z1
Z2 !Z2
Z3 !Z3
Z4 !Z4
Z5 !Z5
Z6 Z6 !Z1 !Z2

NOTE: several relations are degenerate (Z1 !Z1).
