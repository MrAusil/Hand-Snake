from game.score import ScoreKeeper


def test_increment():
    s = ScoreKeeper(None)
    s.add(10)
    s.add(10)
    assert s.score == 20


def test_high_score_tracks_and_flags_record():
    s = ScoreKeeper(None)
    s.add(30)
    assert s.high_score == 30 and s.new_record
    s.reset()
    assert s.score == 0 and s.high_score == 30 and not s.new_record
    s.add(10)
    assert not s.new_record


def test_persistence_roundtrip(tmp_path):
    path = tmp_path / "data" / "highscore.json"
    s = ScoreKeeper(path)
    s.add(70)
    assert s.save() is True
    assert ScoreKeeper(path).high_score == 70


def test_corrupt_file_is_ignored(tmp_path):
    path = tmp_path / "hs.json"
    path.write_text("not json{")
    assert ScoreKeeper(path).high_score == 0


def test_save_skipped_without_record(tmp_path):
    path = tmp_path / "hs.json"
    assert ScoreKeeper(path).save() is False
    assert not path.exists()
