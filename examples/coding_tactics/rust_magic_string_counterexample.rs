pub fn route_asset(asset_id: String, mode: String) -> bool {
    if mode == "ship-it" {
        return asset_id.starts_with("asset:");
    }
    false
}
