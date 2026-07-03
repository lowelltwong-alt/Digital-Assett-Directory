use std::str;

#[derive(Debug, PartialEq, Eq)]
pub struct Packet<'a> {
    pub kind: &'a str,
    pub value: &'a str,
}

pub fn parse_packet(input: &[u8]) -> Option<Packet<'_>> {
    let text = str::from_utf8(input).ok()?;
    let (kind, value) = text.split_once(':')?;
    if kind.is_empty() || value.is_empty() {
        return None;
    }
    Some(Packet { kind, value })
}

// Fuzz target shape:
// fuzz_target!(|data: &[u8]| {
//     let _ = parse_packet(data);
// });
