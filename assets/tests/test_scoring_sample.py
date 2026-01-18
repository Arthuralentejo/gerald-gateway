def test_score_boundaries():
    def score_to_limit(score):
        if score < 0.2: return 0
        if score < 0.4: return 10000
        if score < 0.7: return 40000
        return 100000
    assert score_to_limit(0.0) == 0
    assert score_to_limit(0.39) == 10000
    assert score_to_limit(0.4) == 40000
    assert score_to_limit(0.75) == 100000
