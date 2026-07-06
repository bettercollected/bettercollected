from backend.app.utils.flow_analytics import aggregate_flow_events


def ev(sid, frm, to, ts=0):
    return {"session_id": sid, "from_page": frm, "to_page": to, "created_at": ts}


class TestAggregateFlowEvents:
    def test_empty(self):
        result = aggregate_flow_events([])
        assert result == {
            "totalSessions": 0,
            "submittedSessions": 0,
            "dropOffs": {},
            "transitions": [],
        }

    def test_submitted_session_is_not_a_drop_off(self):
        events = [
            ev("s1", "__welcome__", "p1", 1),
            ev("s1", "p1", "p2", 2),
            ev("s1", "p2", "__submit__", 3),
        ]
        result = aggregate_flow_events(events)
        assert result["totalSessions"] == 1
        assert result["submittedSessions"] == 1
        assert result["dropOffs"] == {}

    def test_abandoned_session_drops_on_last_entered_page(self):
        events = [
            ev("s1", "__welcome__", "p1", 1),
            ev("s1", "p1", "p2", 2),
            # went dark on p2
        ]
        result = aggregate_flow_events(events)
        assert result["submittedSessions"] == 0
        assert result["dropOffs"] == {"p2": 1}

    def test_out_of_order_events_use_timestamps(self):
        events = [
            ev("s1", "p1", "p2", 2),
            ev("s1", "__welcome__", "p1", 1),  # arrives late
        ]
        result = aggregate_flow_events(events)
        assert result["dropOffs"] == {"p2": 1}

    def test_mixed_sessions_and_transition_counts(self):
        events = [
            # session a: submits via a jump from p1
            ev("a", "__welcome__", "p1", 1),
            ev("a", "p1", "__submit__", 2),
            # session b: linear, abandons on p2
            ev("b", "__welcome__", "p1", 1),
            ev("b", "p1", "p2", 2),
            # session c: abandons on p1
            ev("c", "__welcome__", "p1", 1),
        ]
        result = aggregate_flow_events(events)
        assert result["totalSessions"] == 3
        assert result["submittedSessions"] == 1
        assert result["dropOffs"] == {"p2": 1, "p1": 1}
        counts = {(t["from"], t["to"]): t["count"] for t in result["transitions"]}
        assert counts[("__welcome__", "p1")] == 3
        assert counts[("p1", "p2")] == 1
        assert counts[("p1", "__submit__")] == 1

    def test_malformed_events_are_ignored(self):
        events = [
            ev("s1", "__welcome__", "p1", 1),
            {"session_id": "", "from_page": "x", "to_page": "y"},
            {"session_id": "s2", "from_page": None, "to_page": "y"},
        ]
        result = aggregate_flow_events(events)
        assert result["totalSessions"] == 1
