from __future__ import annotations

from conftest import mk_packet
from ew11_analyzer.storage import Storage


def test_add_query_flush(tmp_path):
    st = Storage(tmp_path / "t.db")
    for i in range(5):
        st.add_packet(mk_packet(1000.0 + i, bytes([i, 0xEE]), seq=i + 1))
    st.flush()
    assert st.count() == 5
    pkts = st.query()
    assert [p.seq for p in pkts] == [1, 2, 3, 4, 5]
    st.close()


def test_query_filters(tmp_path):
    st = Storage(tmp_path / "t.db")
    for i in range(10):
        st.add_packet(mk_packet(1000.0 + i, b"\x01", topic="a" if i % 2 else "b", seq=i + 1))
    st.flush()
    assert len(st.query(since=1005.0)) == 5
    assert len(st.query(until=1004.0)) == 5
    assert len(st.query(topic="a")) == 5
    assert [p.seq for p in st.query(newest_first=True, limit=3)] == [10, 9, 8]
    assert [p.seq for p in st.query(before_seq=8, newest_first=True, limit=2)] == [7, 6]
    st.close()


def test_prune_ring(tmp_path):
    st = Storage(tmp_path / "t.db", max_packets=100)
    for i in range(300):
        st.add_packet(mk_packet(1000.0 + i, b"\x01", seq=i + 1))
    st.flush()
    cnt = st.count()
    assert 100 <= cnt <= 200  # pruned in batches
    st.close()


def test_markers_crud(tmp_path):
    st = Storage(tmp_path / "t.db")
    m = st.add_marker(1234.5, "조명")
    assert m.id == 1
    assert st.markers()[0].label == "조명"
    assert st.delete_marker(m.id)
    assert st.markers() == []
    st.close()


def test_persistence_across_open(tmp_path):
    st = Storage(tmp_path / "t.db")
    st.add_packet(mk_packet(1.0, b"\xaa\xbb", seq=1))
    st.flush()
    st.close()
    st2 = Storage(tmp_path / "t.db")
    assert st2.count() == 1
    assert st2.max_seq() == 1
    st2.close()


def test_clear_packets_discards_unflushed_packets(tmp_path):
    st = Storage(tmp_path / "t.db")
    st.add_packet(mk_packet(1.0, b"\xaa\xbb", seq=1))

    st.clear_packets()
    st.flush()

    assert st.count() == 0
    assert st.query() == []
    st.close()


def test_lowering_max_packets_prunes_existing_rows(tmp_path):
    st = Storage(tmp_path / "t.db", max_packets=1000)
    for i in range(300):
        st.add_packet(mk_packet(1000.0 + i, b"\x01", seq=i + 1))
    st.flush()

    st.set_max_packets(100)

    assert st.count() == 100
    assert st.query()[0].seq == 201
    st.close()
