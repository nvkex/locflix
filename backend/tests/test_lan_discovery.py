from app.lan.discovery import decode_packet, encode_packet, _source_from_payload


def test_encode_decode_roundtrip():
    raw = encode_packet({"type": "announce", "seeder_id": "abc", "name": "Box"})
    payload = decode_packet(raw)
    assert payload is not None
    assert payload["magic"] == "locflix-lan-v1"
    assert payload["type"] == "announce"
    assert payload["seeder_id"] == "abc"


def test_reject_bad_magic():
    assert decode_packet(b'{"magic":"nope","type":"announce"}') is None


def test_source_from_payload():
    source = _source_from_payload(
        {
            "seeder_id": "s1",
            "name": "Living Room",
            "host": "192.168.1.20",
            "port": 8787,
            "share_enabled": True,
        }
    )
    assert source is not None
    assert source.base_url == "http://192.168.1.20:8787"
