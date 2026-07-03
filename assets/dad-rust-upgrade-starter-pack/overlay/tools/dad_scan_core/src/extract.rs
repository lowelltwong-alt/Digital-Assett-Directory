use std::path::Path;

pub fn asset_type_hint(path: &Path) -> String {
    let ext = path.extension().and_then(|value| value.to_str()).unwrap_or("").to_ascii_lowercase();
    match ext.as_str() {
        "md" | "markdown" => "markdown",
        "txt" => "text",
        "json" | "jsonl" => "json",
        "yaml" | "yml" => "yaml",
        "toml" => "toml",
        "py" => "python_code",
        "rs" => "rust_code",
        "js" | "ts" | "tsx" | "jsx" => "javascript_typescript_code",
        "sql" => "sql",
        "csv" => "csv",
        "pdf" => "pdf",
        "docx" | "pptx" | "xlsx" => "office_open_xml",
        "png" | "jpg" | "jpeg" | "webp" | "gif" => "image",
        "zip" => "archive",
        _ => "unknown",
    }.to_string()
}
