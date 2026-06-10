use serde::Serialize;
use std::path::{Path, PathBuf};

const SCRIPT_FOLDER_NAME: &str = "MaroubaAbleton";

const INIT_PY: &str = include_str!("../../../marouba-ableton/MaroubaAbleton/__init__.py");
const MANAGER_PY: &str = include_str!("../../../marouba-ableton/MaroubaAbleton/manager.py");
const OSC_INIT_PY: &str =
    include_str!("../../../marouba-ableton/MaroubaAbleton/maroubaosc/__init__.py");
const OSC_PY: &str = include_str!("../../../marouba-ableton/MaroubaAbleton/maroubaosc/osc.py");

#[derive(Debug, Serialize)]
pub(crate) struct AbletonInstallResult {
    pub(crate) installed: bool,
    pub(crate) path: String,
    pub(crate) message: String,
}

pub(crate) fn install_ableton_remote_script(
    pick_folder: bool,
) -> Result<AbletonInstallResult, String> {
    let base = if pick_folder {
        pick_remote_scripts_folder()?
    } else {
        default_remote_scripts_dir()?
    };
    let destination = remote_script_destination(&base);
    write_remote_script(&destination)?;
    Ok(AbletonInstallResult {
        installed: true,
        path: destination.display().to_string(),
        message: "MaroubaAbleton Remote Script installed. Restart Ableton Live and select MaroubaAbleton in Preferences > Link / Tempo / MIDI > Control Surface.".to_string(),
    })
}

pub(crate) fn default_remote_scripts_dir() -> Result<PathBuf, String> {
    let user_profile = std::env::var("USERPROFILE")
        .or_else(|_| std::env::var("HOME"))
        .map_err(|_| "Could not find user profile folder".to_string())?;
    Ok(PathBuf::from(user_profile)
        .join("Documents")
        .join("Ableton")
        .join("User Library")
        .join("Remote Scripts"))
}

fn pick_remote_scripts_folder() -> Result<PathBuf, String> {
    rfd::FileDialog::new()
        .set_title("Choose Ableton Remote Scripts or User Library folder")
        .set_directory(default_remote_scripts_dir().unwrap_or_else(|_| PathBuf::from(".")))
        .pick_folder()
        .ok_or_else(|| "Ableton Remote Script install cancelled".to_string())
}

pub(crate) fn remote_script_destination(selected: &Path) -> PathBuf {
    let file_name = selected
        .file_name()
        .and_then(|value| value.to_str())
        .unwrap_or_default();
    if file_name.eq_ignore_ascii_case(SCRIPT_FOLDER_NAME) {
        return selected.to_path_buf();
    }
    if file_name.eq_ignore_ascii_case("Remote Scripts") {
        return selected.join(SCRIPT_FOLDER_NAME);
    }
    if file_name.eq_ignore_ascii_case("User Library") {
        return selected.join("Remote Scripts").join(SCRIPT_FOLDER_NAME);
    }
    selected.join(SCRIPT_FOLDER_NAME)
}

fn write_remote_script(destination: &Path) -> Result<(), String> {
    std::fs::create_dir_all(destination.join("maroubaosc"))
        .map_err(|error| format!("failed to create Remote Script folder: {error}"))?;
    write_file(&destination.join("__init__.py"), INIT_PY)?;
    write_file(&destination.join("manager.py"), MANAGER_PY)?;
    write_file(
        &destination.join("maroubaosc").join("__init__.py"),
        OSC_INIT_PY,
    )?;
    write_file(&destination.join("maroubaosc").join("osc.py"), OSC_PY)?;
    Ok(())
}

fn write_file(path: &Path, content: &str) -> Result<(), String> {
    std::fs::write(path, content)
        .map_err(|error| format!("failed to write {}: {error}", path.display()))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn destination_accepts_remote_scripts_folder() {
        let selected =
            PathBuf::from(r"C:\Users\Dave\Documents\Ableton\User Library\Remote Scripts");
        assert_eq!(
            remote_script_destination(&selected),
            selected.join(SCRIPT_FOLDER_NAME)
        );
    }

    #[test]
    fn destination_accepts_user_library_folder() {
        let selected = PathBuf::from(r"C:\Users\Dave\Documents\Ableton\User Library");
        assert_eq!(
            remote_script_destination(&selected),
            selected.join("Remote Scripts").join(SCRIPT_FOLDER_NAME)
        );
    }

    #[test]
    fn destination_accepts_existing_script_folder() {
        let selected =
            PathBuf::from(r"D:\Portable\Ableton\User Library\Remote Scripts\MaroubaAbleton");
        assert_eq!(remote_script_destination(&selected), selected);
    }
}
