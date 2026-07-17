import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import find_product_clusters as fpc


def _cluster(cid, uuids):
    return {"cluster_id": cid, "type": "product", "count": len(uuids),
            "photos": [{"uuid": u, "filename": f"{u}.jpeg"} for u in uuids]}


def test_filter_live_sorted_drops_photos_and_empty_clusters():
    clusters = [_cluster(1, ["a", "b"]), _cluster(2, ["c"])]
    out, hidden = fpc.filter_live_sorted(clusters, {"b", "c"})
    assert hidden == 2
    assert len(out) == 1 and out[0]["count"] == 1
    assert out[0]["photos"][0]["uuid"] == "a"


def test_filter_live_sorted_noop_without_matches():
    clusters = [_cluster(1, ["a"])]
    out, hidden = fpc.filter_live_sorted(clusters, set())
    assert out is clusters and hidden == 0
