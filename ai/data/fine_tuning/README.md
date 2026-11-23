# Supervised-learning data preparation

The new personalized question-generation pilot is prepared separately by
`python -m roleready_training.data`. See `../../docs/PERSONALIZED_SFT_DATA.md`.
It contains 256 fictional scenarios, partitioned by project family into
192 train / 32 validation / 32 test inputs. Draft targets are NOT approved data.
The exporter requires two explicit human approvals of each exact input+target.
No fine-tuning is launched by preparation, and no generated criterion becomes
a Prometheus reference answer. Bodies, journals and reviews remain ignored/local.

The original Mission 003 did not introduce training data or a training run.

This is a distinct, ignored destination for future reviewed, licensed instruction
examples and their train/validation/test partitions. Keep CV/job-conditioned
examples separate from general interview Q&A. Establish grouping, duplicate and
leakage policies before exporting training data; never use retrieval evaluation
queries, benchmark C, or generation-evaluation scenarios as SFT examples.

The versioned retrieval corpus at `../mission003/processed/corpus.jsonl` is a
searchable knowledge collection, not a training split. Its records explicitly
reject the legacy SFT loader. Existing `roleready_ai.datasets` splitting and
`roleready_ai.sft` reviewed-TRAIN export remain supported for legacy banks.

Keep future candidate content private. Approval of a publisher's dataset license
does not approve technical answers, reference criteria or candidate consent.
