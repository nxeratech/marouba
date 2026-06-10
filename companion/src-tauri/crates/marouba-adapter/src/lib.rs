use serde::{Deserialize, Serialize};
use serde_yaml::Value;
use std::collections::BTreeMap;

pub type Capabilities = BTreeMap<String, String>;

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "UPPERCASE")]
pub enum AdapterTier {
    T0,
    T1,
    T2,
    T3,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct AdapterManifest {
    pub adapter: String,
    pub mechanism: String,
    pub tier: AdapterTier,
    pub versions: Vec<String>,
    #[serde(default)]
    pub capabilities: Capabilities,
    #[serde(default)]
    pub known_blockers: Vec<String>,
    pub setup: String,
}

impl AdapterManifest {
    pub fn from_yaml(input: &str) -> Result<Self, ManifestError> {
        let manifest: Self = serde_yaml::from_str(input)?;
        manifest.validate()?;
        Ok(manifest)
    }

    pub fn to_yaml(&self) -> Result<String, ManifestError> {
        self.validate()?;
        Ok(serde_yaml::to_string(self)?)
    }

    pub fn validate(&self) -> Result<(), ManifestError> {
        require_non_empty("adapter", &self.adapter)?;
        require_non_empty("mechanism", &self.mechanism)?;
        require_non_empty("setup", &self.setup)?;
        if self.versions.is_empty()
            || self
                .versions
                .iter()
                .any(|version| version.trim().is_empty())
        {
            return Err(ManifestError::InvalidField(
                "versions must contain at least one non-empty version range".to_string(),
            ));
        }
        if self.capabilities.keys().any(|key| key.trim().is_empty()) {
            return Err(ManifestError::InvalidField(
                "capability names must be non-empty".to_string(),
            ));
        }
        if self
            .capabilities
            .values()
            .any(|value| value.trim().is_empty())
        {
            return Err(ManifestError::InvalidField(
                "capability values must be non-empty".to_string(),
            ));
        }
        Ok(())
    }
}

fn require_non_empty(field: &str, value: &str) -> Result<(), ManifestError> {
    if value.trim().is_empty() {
        Err(ManifestError::InvalidField(format!(
            "{field} must be non-empty"
        )))
    } else {
        Ok(())
    }
}

#[derive(Debug, thiserror::Error)]
pub enum ManifestError {
    #[error("manifest yaml error: {0}")]
    Yaml(#[from] serde_yaml::Error),
    #[error("invalid manifest: {0}")]
    InvalidField(String),
}

pub trait MaroubaAdapter: Send + Sync {
    fn manifest(&self) -> AdapterManifest;
    fn health_check(&self) -> AdapterHealth;
    fn subscribe(&self) -> EventStream;
    fn resolve_value(&self, element: ElementRef) -> Option<Value>;
    fn execute(&self, step: &VaultStep) -> StepResult;
    fn snapshot_state(&self) -> AppStateSnapshot;
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum AdapterHealthStatus {
    Ok,
    Degraded,
    Unavailable,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct AdapterHealth {
    pub status: AdapterHealthStatus,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub message: Option<String>,
}

impl AdapterHealth {
    pub fn ok() -> Self {
        Self {
            status: AdapterHealthStatus::Ok,
            message: None,
        }
    }

    pub fn unavailable(message: impl Into<String>) -> Self {
        Self {
            status: AdapterHealthStatus::Unavailable,
            message: Some(message.into()),
        }
    }
}

pub type EventStream = Vec<AdapterEvent>;

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct AdapterEvent {
    pub event_type: String,
    #[serde(default)]
    pub timestamp_ms: u64,
    #[serde(default)]
    pub payload: BTreeMap<String, Value>,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
pub struct ElementRef {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub app: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub window_title: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub element_name: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub role: Option<String>,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct VaultStep {
    pub id: String,
    #[serde(rename = "type")]
    pub step_type: String,
    pub intent: String,
    #[serde(default)]
    pub routes: Vec<RouteSpec>,
    #[serde(default)]
    pub signals: BTreeMap<String, Value>,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct RouteSpec {
    #[serde(rename = "type")]
    pub route_type: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub map_group: Option<RouteGroup>,
    #[serde(default)]
    pub payload: BTreeMap<String, Value>,
}

#[derive(Clone, Debug, Deserialize, Eq, PartialEq, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum RouteGroup {
    R1,
    R2,
    R3,
    R4,
}

#[derive(Clone, Debug, Deserialize, PartialEq, Serialize)]
pub struct StepResult {
    pub success: bool,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub route_used: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub output: Option<Value>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
}

impl StepResult {
    pub fn success(route_used: impl Into<String>) -> Self {
        Self {
            success: true,
            route_used: Some(route_used.into()),
            output: None,
            error: None,
        }
    }

    pub fn failed(error: impl Into<String>) -> Self {
        Self {
            success: false,
            route_used: None,
            output: None,
            error: Some(error.into()),
        }
    }
}

#[derive(Clone, Debug, Default, Deserialize, PartialEq, Serialize)]
pub struct AppStateSnapshot {
    #[serde(default)]
    pub values: BTreeMap<String, Value>,
}

#[derive(Clone, Debug)]
pub struct StubAdapter {
    manifest: AdapterManifest,
}

impl StubAdapter {
    pub fn new(manifest: AdapterManifest) -> Self {
        Self { manifest }
    }
}

impl MaroubaAdapter for StubAdapter {
    fn manifest(&self) -> AdapterManifest {
        self.manifest.clone()
    }

    fn health_check(&self) -> AdapterHealth {
        AdapterHealth::ok()
    }

    fn subscribe(&self) -> EventStream {
        Vec::new()
    }

    fn resolve_value(&self, _element: ElementRef) -> Option<Value> {
        None
    }

    fn execute(&self, step: &VaultStep) -> StepResult {
        StepResult::success(format!("stub:{}", step.id))
    }

    fn snapshot_state(&self) -> AppStateSnapshot {
        AppStateSnapshot::default()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const ABLETON_MANIFEST: &str = r#"
adapter: ableton-live
mechanism: remote-script + osc
tier: T1
versions: ["11.x", "12.x"]
capabilities:
  parameter_values: full
  midi_notes: full
  transport_state: full
  file_drag_payload: partial
  custom_renderer_widgets: via_api
known_blockers: []
setup: one-time remote script install (installer-automated)
"#;

    #[test]
    fn ableton_manifest_from_master_plan_parses_and_validates() {
        let manifest = AdapterManifest::from_yaml(ABLETON_MANIFEST).expect("parse manifest");

        assert_eq!(manifest.adapter, "ableton-live");
        assert_eq!(manifest.tier, AdapterTier::T1);
        assert_eq!(manifest.versions, vec!["11.x", "12.x"]);
        assert_eq!(
            manifest.capabilities.get("custom_renderer_widgets"),
            Some(&"via_api".to_string())
        );
        manifest.validate().expect("valid manifest");
    }

    #[test]
    fn manifest_round_trips_yaml() {
        let manifest = AdapterManifest::from_yaml(ABLETON_MANIFEST).expect("parse manifest");
        let yaml = manifest.to_yaml().expect("serialize manifest");
        let reparsed = AdapterManifest::from_yaml(&yaml).expect("reparse manifest");

        assert_eq!(reparsed, manifest);
    }

    #[test]
    fn manifest_validation_rejects_missing_versions() {
        let yaml = r#"
adapter: paint
mechanism: gesture
 tier: T3
versions: []
capabilities: {}
known_blockers: []
setup: none
"#;
        let result = AdapterManifest::from_yaml(yaml);

        assert!(result.is_err());
    }

    #[test]
    fn stub_adapter_implements_every_trait_method() {
        let manifest = AdapterManifest::from_yaml(ABLETON_MANIFEST).expect("parse manifest");
        let adapter = StubAdapter::new(manifest.clone());
        let step = VaultStep {
            id: "step_001".to_string(),
            step_type: "noop".to_string(),
            intent: "prove trait surface".to_string(),
            routes: vec![RouteSpec {
                route_type: "api".to_string(),
                map_group: Some(RouteGroup::R1),
                payload: BTreeMap::new(),
            }],
            signals: BTreeMap::new(),
        };

        assert_eq!(adapter.manifest(), manifest);
        assert_eq!(adapter.health_check().status, AdapterHealthStatus::Ok);
        assert!(adapter.subscribe().is_empty());
        assert!(adapter
            .resolve_value(ElementRef {
                app: Some("Ableton Live".to_string()),
                window_title: None,
                element_name: Some("Send A".to_string()),
                role: None,
            })
            .is_none());
        assert!(adapter.execute(&step).success);
        assert!(adapter.snapshot_state().values.is_empty());
    }
}
