use marouba_adapter::AdapterManifest;
use std::env;
use std::fs;
use std::process;

fn main() {
    let Some(path) = env::args().nth(1) else {
        eprintln!("usage: dump_manifest <manifest.yaml>");
        process::exit(2);
    };

    let input = fs::read_to_string(&path).unwrap_or_else(|error| {
        eprintln!("failed to read {path}: {error}");
        process::exit(2);
    });
    let manifest = AdapterManifest::from_yaml(&input).unwrap_or_else(|error| {
        eprintln!("failed to parse {path}: {error}");
        process::exit(1);
    });
    println!(
        "{}",
        serde_json::to_string(&manifest).expect("manifest serializes as JSON")
    );
}
