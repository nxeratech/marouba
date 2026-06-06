---
app: Browser
app_version: Chrome/Edge latest
platform: windows
api_base: http://127.0.0.1:9222
endpoints:
  chrome_devtools_version: /json/version
  chrome_devtools_tabs: /json
  chrome_devtools_protocol: ws://127.0.0.1:9222/devtools/page/{target_id}
uia_window_title: Google Chrome|Microsoft Edge
uia_elements:
  address_bar: Address and search bar
  reload_button: Reload
  submit_button: Submit
  file_picker: Open
shortcuts:
  address_bar: [ctrl, l]
  reload: [ctrl, r]
  devtools: [ctrl, shift, i]
  print: [ctrl, p]
cli_commands:
  chrome_headless_screenshot: "chrome --headless --disable-gpu --screenshot={output_path} --window-size={width},{height} {url}"
  edge_headless_screenshot: "msedge --headless --disable-gpu --screenshot={output_path} --window-size={width},{height} {url}"
install_paths:
  - C:\Program Files\Google\Chrome\Application\chrome.exe
  - C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe
output_folder: C:\Users\Dave\Pictures\Marouba\Browser
---

# Browser Profile

Browser automation prefers the Chrome DevTools Protocol or headless CLI. UIA routes cover normal user sessions where remote debugging is not enabled.
