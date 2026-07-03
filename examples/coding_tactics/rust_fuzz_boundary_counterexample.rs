pub fn parse_packet(input: &[u8]) -> (&str, &str) {
    // Panics on invalid UTF-8, missing separators, and empty packets.
    let text = std::str::from_utf8(input).unwrap();
    text.split_once(':').unwrap()
}
