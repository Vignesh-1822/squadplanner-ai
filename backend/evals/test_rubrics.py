"""Rubric structure is stable enough for human/model calibration."""

from evals.rubrics import RUBRIC_FILES, load_all, load_rubric, rubric_version


def test_all_three_rubrics_have_five_substantive_anchors():
    rubrics = load_all()
    assert tuple(rubrics) == RUBRIC_FILES
    for name, rubric in rubrics.items():
        assert rubric == load_rubric(name)
        assert set(rubric["anchors"]) == {1, 2, 3, 4, 5}
        for anchor in rubric["anchors"].values():
            assert len(anchor["label"]) >= 5
            assert len(anchor["description"]) >= 100


def test_rubric_version_is_a_stable_sha256():
    first = rubric_version()
    assert first == rubric_version()
    assert len(first) == 64
    int(first, 16)
