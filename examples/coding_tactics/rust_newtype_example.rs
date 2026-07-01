#[derive(Clone, Debug, Eq, PartialEq, Hash)]
pub struct AssetId(String);

impl AssetId {
    pub fn new(value: impl Into<String>) -> Result<Self, String> {
        let value = value.into();
        if value.starts_with("asset:") {
            Ok(Self(value))
        } else {
            Err("asset IDs must start with asset:".to_string())
        }
    }

    pub fn as_str(&self) -> &str {
        &self.0
    }
}
