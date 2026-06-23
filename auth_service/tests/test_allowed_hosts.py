import pytest

from validators import host_matches, parse_allowed_hosts


class TestParseAllowedHosts:
    def test_empty_string(self):
        assert parse_allowed_hosts("") == []

    def test_trailing_comma(self):
        assert parse_allowed_hosts("a.com,") == ["a.com"]

    def test_combo(self):
        assert parse_allowed_hosts("  Example.COM ,  Other.COM  ") == [
            "example.com",
            "other.com",
        ]


class TestHostMatches:
    def test_exact_match(self):
        assert host_matches("example.com", "example.com") is True

    def test_exact_case_insensitive(self):
        assert host_matches("EXAMPLE.com", "example.com") is True

    def test_exact_mismatch(self):
        assert host_matches("evil.com", "example.com") is False

    def test_exact_with_port_match(self):
        assert host_matches("example.com:8080", "example.com:8080") is True

    def test_exact_with_port_mismatch(self):
        assert host_matches("example.com:9090", "example.com:8080") is False

    def test_pattern_no_port_request_has_port(self):
        assert host_matches("example.com:8080", "example.com") is False

    def test_pattern_has_port_request_no_port(self):
        assert host_matches("example.com", "example.com:8080") is False

    @pytest.mark.parametrize("subdomain", ["api", "cdn"])
    def test_wildcard_matches_single_label(self, subdomain):
        assert host_matches(f"{subdomain}.example.com", "*.example.com") is True

    def test_wildcard_no_match_bare_domain(self):
        assert host_matches("example.com", "*.example.com") is False

    def test_wildcard_no_match_multi_label(self):
        assert host_matches("x.y.example.com", "*.example.com") is False

    def test_wildcard_no_match_different_suffix(self):
        assert host_matches("api.other.com", "*.example.com") is False

    def test_wildcard_no_match_partial_suffix(self):
        assert host_matches("api.otherexample.com", "*.example.com") is False

    def test_wildcard_case_insensitive(self):
        assert host_matches("API.Example.COM", "*.example.com") is True

    def test_wildcard_with_port_match(self):
        assert host_matches("api.example.com:8080", "*.example.com:8080") is True

    def test_wildcard_with_port_mismatch(self):
        assert host_matches("api.example.com:9090", "*.example.com:8080") is False

    def test_wildcard_pattern_no_port_request_has_port(self):
        assert host_matches("api.example.com:8080", "*.example.com") is False

    def test_wildcard_pattern_has_port_request_no_port(self):
        assert host_matches("api.example.com", "*.example.com:8080") is False

    def test_match_all_any_hostname(self):
        assert host_matches("anything.example.com", "*") is True

    def test_match_all_any_with_port(self):
        assert host_matches("anything.example.com:1234", "*") is True

    def test_match_all_with_port_match(self):
        assert host_matches("anything.example.com:8080", "*:8080") is True

    def test_match_all_with_port_mismatch(self):
        assert host_matches("anything.example.com:9090", "*:8080") is False

    def test_ipv4_match(self):
        assert host_matches("192.168.1.1", "192.168.1.1") is True

    def test_ipv4_with_port_match(self):
        assert host_matches("192.168.1.1:3000", "192.168.1.1:3000") is True

    def test_ipv4_port_mismatch(self):
        assert host_matches("192.168.1.1:3000", "192.168.1.1:4000") is False

    def test_empty_requested_host(self):
        assert host_matches("", "example.com") is False
