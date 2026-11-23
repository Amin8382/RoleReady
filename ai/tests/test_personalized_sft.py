"""Authored fixtures only. Test reviewer identities are never real approvals."""
import json
from copy import deepcopy

import pytest

from roleready_training import data
from roleready_ai.tracking import read_json, digest


def exclusion():
    return {"input_texts": [], "question_sha256": [], "source_sha256": {"fixture": "test-only"}}


def test_balanced_project_family_splits_and_no_eval_reuse():
    values = data.make_scenarios()
    assert len(values) == 256
    data.check_inputs(values, exclusion())
    for split, count in (("train", 192), ("validation", 32), ("test", 32)):
        selected = [v for v in values if v["split"] == split]
        assert len(selected) == count
        assert len({(v['target_role'], v['experience_level']) for v in selected}) == 32
    evaluation = data.read_json(data.ROOT / 'ai/evaluation/ablation/scenarios.json')
    data.check_inputs(values, {**exclusion(), "input_texts": [data.normalized(s['cv_text']) for s in evaluation]})
    contaminated = deepcopy(values)
    contaminated[0]['cv_text'] = evaluation[0]['cv_text']
    with pytest.raises(ValueError, match="overlapping"):
        data.check_inputs(contaminated, {**exclusion(), "input_texts": [data.normalized(evaluation[0]['cv_text'])]})
    contaminated = deepcopy(values)
    contaminated[1]['split'] = 'test' if contaminated[0]['split'] != 'test' else 'train'
    with pytest.raises(ValueError, match="family"):
        data.check_inputs(contaminated, exclusion())


def test_prepare_produces_no_approved_or_trainable_targets(monkeypatch, tmp_path):
    monkeypatch.setattr(data, 'reserved', exclusion)
    out = tmp_path / 'pilot'
    manifest = data.prepare(out)
    assert manifest['ready_for_training'] is False
    assert manifest['split_counts'] == {'train':192, 'validation':32, 'test':32}
    with pytest.raises(FileExistsError): data.prepare(out)
    data.review_pack(out, out / 'review')
    with pytest.raises((ValueError, TypeError)):
        data.export(out, out/'review/targets.jsonl', [out/'review/reviewer-1.jsonl',out/'review/reviewer-2.jsonl'],out/'release')
    assert not (out/'release').exists()


def target(source):
    from roleready_ai.generation import evidence_excerpts, EVIDENCE_PURPOSE
    reason = f"CV: [{evidence_excerpts(source['cv_text'])[0]}]; Job: [{evidence_excerpts(source['job_description'])[0]}]. {EVIDENCE_PURPOSE}"
    texts = ["How would you validate missing records in a report?", "How would you prevent double counting in a join?",
        "How would you communicate uncertainty to a colleague?", "How would you test a change before releasing it?",
        "How would you prioritize competing requests?", "How would you investigate a surprising result?",
        "How would you learn an unfamiliar tool?"]
    return {'questions':[{'text':text,'target_skill':'analysis','difficulty':'medium','reason_for_asking':reason,
        'reference_criteria':['The answer should explain a proposed validation method.'],'source_ids':[]} for text in texts]}


def test_target_contract_and_excluded_question_guard():
    source = data.make_scenarios()[0]
    proposed = target(source)
    data.validate_target(source, proposed, exclusion())
    with pytest.raises(ValueError, match="excluded"):
        data.validate_target(source, proposed, {**exclusion(), 'question_sha256':[digest(data.normalized(proposed['questions'][0]['text']))]})
    proposed['questions'][0]['source_ids'] = ['rrq-not-in-prompt']
    with pytest.raises(ValueError): data.validate_target(source, proposed, exclusion())


def test_clean_sft_prompt_matches_inference_without_retry_or_rag():
    source = data.make_scenarios()[0]
    messages = data.clean_messages(source)
    context = json.loads(messages[1]['content'][messages[1]['content'].rfind('\n{')+1:])
    assert context['retrieved_sources'] == [] and context['retrieved_source_ids'] == []
    assert context['cv_text_untrusted'] == source['cv_text']
    assert 'Previous attempt failed' not in messages[1]['content']


def test_human_approval_gate_binds_exact_target_and_distinct_identities(monkeypatch, tmp_path):
    monkeypatch.setattr(data, 'reserved', exclusion)
    dataset = tmp_path/'pilot'; data.prepare(dataset)
    values = data.rows(dataset/'scenarios.jsonl')
    targets, first, second = [], [], []
    for source in values:
        proposed = target(source)
        fingerprint = digest({'input':source,'target':proposed})
        targets.append({'record_id':source['record_id'],'input':source,'target':proposed})
        approval = {'record_id':source['record_id'],'approval_sha256':fingerprint,'status':'human_approved',
            'reviewed_at':'2026-11-23','reviewer':'TEST-ONLY-REVIEWER-1','checks':dict.fromkeys(data.CHECKS,True)}
        first.append(approval)
        second.append({**approval,'reviewer':'TEST-ONLY-REVIEWER-2'})
    data.write_rows(dataset/'targets.jsonl',targets)
    data.write_rows(dataset/'first.jsonl',first)
    second[0]['approval_sha256'] = 'stale'
    data.write_rows(dataset/'second.jsonl',second)
    with pytest.raises(ValueError,match='stale'):
        data.export(dataset,dataset/'targets.jsonl',[dataset/'first.jsonl',dataset/'second.jsonl'],dataset/'blocked')
    second[0]['approval_sha256'] = first[0]['approval_sha256']
    second[0]['reviewer'] = first[0]['reviewer']
    data.write_rows(dataset/'same-human.jsonl',second)
    with pytest.raises(ValueError,match='distinct'):
        data.export(dataset,dataset/'targets.jsonl',[dataset/'first.jsonl',dataset/'same-human.jsonl'],dataset/'blocked')
    second[0]['reviewer'] = 'TEST-ONLY-REVIEWER-2'
    data.write_rows(dataset/'valid-second.jsonl',second)
    report = data.export(dataset,dataset/'targets.jsonl',[dataset/'first.jsonl',dataset/'valid-second.jsonl'],dataset/'release')
    assert report['counts'] == {'train':192,'validation':32,'test':32}
    assert len(data.rows(dataset/'release/train.jsonl')) == 192
    assert all(r['split']=='train' for r in data.rows(dataset/'release/train.jsonl'))
