use marouba_adapter::{
    AdapterHealth, AdapterManifest, AdapterTier, AppStateSnapshot, ElementRef, EventStream,
    MaroubaAdapter, StepResult, VaultStep,
};
use std::collections::BTreeMap;

#[derive(Clone, Debug, Default)]
pub(crate) struct PaintNullAdapter;

impl PaintNullAdapter {
    pub(crate) fn id() -> &'static str {
        "ms-paint"
    }
}

impl MaroubaAdapter for PaintNullAdapter {
    fn manifest(&self) -> AdapterManifest {
        AdapterManifest {
            adapter: Self::id().to_string(),
            mechanism: "null-adapter + gesture".to_string(),
            tier: AdapterTier::T3,
            versions: vec!["Windows 10".to_string(), "Windows 11".to_string()],
            capabilities: BTreeMap::from([
                ("canvas_strokes".to_string(), "gesture".to_string()),
                ("shape_drags".to_string(), "gesture".to_string()),
                ("toolbar_controls".to_string(), "gesture".to_string()),
                ("parameter_values".to_string(), "none".to_string()),
            ]),
            known_blockers: Vec::new(),
            setup: "bundled Windows Paint application".to_string(),
        }
    }

    fn health_check(&self) -> AdapterHealth {
        AdapterHealth::ok()
    }

    fn subscribe(&self) -> EventStream {
        Vec::new()
    }

    fn resolve_value(&self, _element: ElementRef) -> Option<serde_yaml::Value> {
        None
    }

    fn execute(&self, step: &VaultStep) -> StepResult {
        if step
            .routes
            .iter()
            .any(|route| route.route_type == "gesture")
        {
            StepResult::success("gesture")
        } else {
            StepResult::failed("Paint null adapter only supports gesture routes")
        }
    }

    fn snapshot_state(&self) -> AppStateSnapshot {
        AppStateSnapshot::default()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use marouba_adapter::{RouteGroup, RouteSpec};

    #[test]
    fn paint_null_adapter_manifest_is_t3_gesture_only() {
        let adapter = PaintNullAdapter;
        let manifest = adapter.manifest();

        assert_eq!(manifest.adapter, "ms-paint");
        assert_eq!(manifest.tier, AdapterTier::T3);
        assert_eq!(manifest.mechanism, "null-adapter + gesture");
        assert_eq!(
            manifest.capabilities.get("canvas_strokes"),
            Some(&"gesture".to_string())
        );
        assert_eq!(
            manifest.capabilities.get("parameter_values"),
            Some(&"none".to_string())
        );
    }

    #[test]
    fn paint_null_adapter_executes_only_gesture_steps() {
        let adapter = PaintNullAdapter;
        let gesture_step = VaultStep {
            id: "step_001".to_string(),
            step_type: "legacy_gesture_sequence".to_string(),
            intent: "Replay Paint gesture.".to_string(),
            routes: vec![RouteSpec {
                route_type: "gesture".to_string(),
                map_group: Some(RouteGroup::R3),
                payload: BTreeMap::new(),
            }],
            signals: BTreeMap::new(),
        };
        let uia_step = VaultStep {
            id: "step_002".to_string(),
            step_type: "toolbar_click".to_string(),
            intent: "Click Paint toolbar.".to_string(),
            routes: vec![RouteSpec {
                route_type: "uia".to_string(),
                map_group: Some(RouteGroup::R2),
                payload: BTreeMap::new(),
            }],
            signals: BTreeMap::new(),
        };

        assert_eq!(
            adapter.execute(&gesture_step).route_used,
            Some("gesture".to_string())
        );
        assert!(!adapter.execute(&uia_step).success);
    }
}
