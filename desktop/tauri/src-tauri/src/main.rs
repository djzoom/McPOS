use std::process::{Command, Stdio};
use std::path::PathBuf;
use std::fs::{File, OpenOptions};
use std::io::Write;
use std::time::Duration;
use std::sync::{Arc, Mutex, LazyLock};
use tauri::{AppHandle, Manager, Window};
use serde_json::Value;

const MAX_STARTUP_SECONDS: u64 = 20;
const PORT_RANGE: (u16, u16) = (8000, 8010);
const DEFAULT_PORT: u16 = 8010;

// Global backend process handle
static BACKEND_PROCESS: LazyLock<Arc<Mutex<Option<std::process::Child>>>> = LazyLock::new(|| Arc::new(Mutex::new(None)));

#[tauri::command]
fn get_api_port() -> u16 {
    std::env::var("API_PORT")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(8000)
}

fn find_python_executable() -> PathBuf {
    // Try repo venv first
    let repo_root = std::env::current_exe()
        .ok()
        .and_then(|exe| {
            exe.parent()
                .map(|p| p.to_path_buf())
                .and_then(|p| p.parent().map(|pp| pp.to_path_buf()))
                .and_then(|p| p.parent().map(|pp| pp.to_path_buf()))
        })
        .unwrap_or_else(|| PathBuf::from("."));

    let venv_paths = vec![
        repo_root.join("kat_rec_web").join(".venv311").join("bin").join("python"),
        repo_root.join(".venv311").join("bin").join("python"),
        repo_root.join(".venv").join("bin").join("python"),
        PathBuf::from("python3"),
        PathBuf::from("python"),
    ];

    for path in &venv_paths {
        if path.exists() && path.is_file() {
            return path.clone();
        }
        // Try to find in PATH
        if let Ok(output) = Command::new(path).arg("--version").output() {
            if output.status.success() {
                return path.clone();
            }
        }
    }

    // Fallback to python3
    PathBuf::from("python3")
}

fn get_backend_dir() -> PathBuf {
    let repo_root = std::env::current_exe()
        .ok()
        .and_then(|exe| {
            exe.parent()
                .map(|p| p.to_path_buf())
                .and_then(|p| p.parent().map(|pp| pp.to_path_buf()))
                .and_then(|p| p.parent().map(|pp| pp.to_path_buf()))
        })
        .unwrap_or_else(|| PathBuf::from("."));

    repo_root.join("kat_rec_web").join("backend")
}

fn setup_logging() -> std::io::Result<File> {
    // Use desktop/tauri/backend.log (relative to repo root)
    let repo_root = std::env::current_exe()
        .ok()
        .and_then(|exe| {
            exe.parent()
                .map(|p| p.to_path_buf())
                .and_then(|p| p.parent().map(|pp| pp.to_path_buf()))
                .and_then(|p| p.parent().map(|pp| pp.to_path_buf()))
        })
        .unwrap_or_else(|| PathBuf::from("."));
    
    let log_dir = repo_root.join("desktop").join("tauri");
    std::fs::create_dir_all(&log_dir).ok();
    
    let log_file = log_dir.join("backend.log");
    
    // Simple rotation: if > 1MB, rename and create new (keep 5 files)
    if log_file.exists() {
        if let Ok(metadata) = std::fs::metadata(&log_file) {
            if metadata.len() > 1_000_000 {
                // Rotate: keep 5 files
                for i in (1..=4).rev() {
                    let old = log_dir.join(format!("backend.{}.log", i));
                    let new = log_dir.join(format!("backend.{}.log", i + 1));
                    if old.exists() {
                        let _ = std::fs::rename(&old, &new);
                    }
                }
                let _ = std::fs::rename(&log_file, log_dir.join("backend.1.log"));
            }
        }
    }
    
    OpenOptions::new()
        .create(true)
        .append(true)
        .open(&log_file)
}

fn write_log(file: &mut File, msg: &str) {
    let timestamp = chrono::Utc::now().format("%Y-%m-%d %H:%M:%S UTC");
    if let Err(e) = writeln!(file, "[{}] {}", timestamp, msg) {
        eprintln!("Failed to write log: {}", e);
    }
}

#[tauri::command]
async fn start_backend(app: AppHandle) -> Result<String, String> {
    let python = find_python_executable();
    let backend_dir = get_backend_dir();
    let mut log_file = setup_logging().map_err(|e| format!("Failed to setup logging: {}", e))?;

    write_log(&mut log_file, "Starting backend...");

    // Try DEFAULT_PORT first, then fall back to range
    let ports_to_try = vec![DEFAULT_PORT].into_iter()
        .chain(PORT_RANGE.0..=PORT_RANGE.1)
        .collect::<std::vec::Vec<_>>();
    
    for port in ports_to_try {
        let port_str = port.to_string();
        
        // Check if port is available
        if let Ok(response) = reqwest::get(&format!("http://127.0.0.1:{}", port)).await {
            if response.status().is_success() {
                // Port already in use, try next
                continue;
            }
        }

        let mut env = std::env::vars().collect::<std::collections::HashMap<_, _>>();
        env.insert("API_PORT".to_string(), port_str.clone());
        env.insert("USE_MOCK_MODE".to_string(), "false".to_string());

        let mut cmd = Command::new(&python);
        cmd.arg("-m")
           .arg("uvicorn")
           .arg("main:app")
           .arg("--host")
           .arg("127.0.0.1")
           .arg("--port")
           .arg(&port_str)
           .current_dir(&backend_dir)
           .envs(&env)
           .stdout(Stdio::piped())
           .stderr(Stdio::piped());

        write_log(&mut log_file, &format!("Attempting to start on port {}", port));

        match cmd.spawn() {
            Ok(child) => {
                // Store process handle
                *BACKEND_PROCESS.lock().unwrap() = Some(child);
                
                // Wait for readiness
                let mut ready = false;
                for _ in 0..MAX_STARTUP_SECONDS {
                    if let Ok(response) = reqwest::get(&format!("http://127.0.0.1:{}/health", port)).await {
                        if response.status().is_success() {
                            if let Ok(json) = response.json::<Value>().await {
                                if json.get("status").and_then(|s| s.as_str()) == Some("ok") {
                                    ready = true;
                                    write_log(&mut log_file, &format!("Backend ready on port {}", port));
                                    break;
                                }
                            }
                        }
                    }
                    tokio::time::sleep(Duration::from_secs(1)).await;
                }

                if ready {
                    if let Some(window) = app.get_window("main") {
                        let _ = window.emit("backend-ready", &port_str);
                    }
                    return Ok(port_str);
                } else {
                    // Kill process
                    if let Some(mut child) = BACKEND_PROCESS.lock().unwrap().take() {
                        let _ = child.kill();
                    }
                    write_log(&mut log_file, &format!("Backend failed to become ready on port {}", port));
                }
            }
            Err(e) => {
                write_log(&mut log_file, &format!("Failed to spawn backend: {}", e));
            }
        }
    }

    Err("Failed to start backend on any available port".to_string())
}

#[tauri::command]
async fn inject_api_base(window: Window, port: u16) -> Result<(), String> {
    let api_base = format!("http://127.0.0.1:{}", port);
    let ws_base = format!("ws://127.0.0.1:{}", port);

    window.eval(&format!(
        r#"
        (function() {{
            window.__API_BASE__ = '{}';
            window.__WS_BASE__ = '{}';
            console.log('Injected API base:', window.__API_BASE__);
        }})();
        "#,
        api_base, ws_base
    )).map_err(|e| format!("Failed to inject API base: {}", e))?;

    Ok(())
}

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![start_backend, get_api_port, inject_api_base])
        .setup(|app| {
            let window = app.get_window("main").unwrap();
            
            // Show splash screen
            window.eval(r#"
                document.body.innerHTML = `
                    <div style="
                        display: flex;
                        flex-direction: column;
                        align-items: center;
                        justify-content: center;
                        height: 100vh;
                        background: linear-gradient(135deg, #202020 0%, #2a2a2a 100%);
                        color: #ffffff;
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                        animation: fadeIn 3s ease-in;
                    ">
                        <h1 style="font-size: 2em; margin-bottom: 1em; color: #00ff66;">Mission Control Loading…</h1>
                        <div style="width: 200px; height: 4px; background: #333; border-radius: 2px; overflow: hidden;">
                            <div id="loader" style="height: 100%; background: #00ff66; width: 0%; animation: progress 2s infinite;"></div>
                        </div>
                    </div>
                    <style>
                        @keyframes fadeIn {
                            from { opacity: 0; }
                            to { opacity: 1; }
                        }
                        @keyframes progress {
                            0% { width: 0%; }
                            50% { width: 70%; }
                            100% { width: 100%; }
                        }
                    </style>
                `;
            "#).unwrap();
            
            // Start backend and navigate to /t2r
            let window_clone = window.clone();
            let app_handle = app.app_handle();
            
            tauri::async_runtime::spawn(async move {
                match start_backend(app_handle.clone()).await {
                    Ok(port_str) => {
                        let port: u16 = port_str.parse().unwrap_or(8000);
                        
                        // Inject API base
                        if let Err(e) = inject_api_base(window_clone.clone(), port).await {
                            eprintln!("Failed to inject API base: {}", e);
                        }
                        
                        // Navigate to /t2r using eval
                        let _ = window_clone.eval(r#"window.location.href = '/t2r/';"#);
                    }
                    Err(e) => {
                        eprintln!("Failed to start backend: {}", e);
                        window_clone.eval(&format!(
                            r#"
                            document.body.innerHTML = '<div style="padding: 20px; font-family: sans-serif; background: #202020; color: #ffffff;">
                                <h1>Failed to Start Backend</h1>
                                <p>{}</p>
                                <p>Please check desktop/tauri/backend.log for details.</p>
                            </div>';
                            "#,
                            e.replace("'", "\\'")
                        )).unwrap();
                    }
                }
            });

            Ok(())
        })
        .on_window_event(|event| {
            if let tauri::WindowEvent::CloseRequested { .. } = event.event() {
                // Graceful shutdown
                if let Some(mut child) = BACKEND_PROCESS.lock().unwrap().take() {
                    // Try graceful shutdown
                    #[cfg(unix)]
                    {
                        // On Unix, kill() sends SIGTERM
                        if let Err(e) = child.kill() {
                            eprintln!("Failed to kill backend: {}", e);
                        } else {
                            // Wait up to 3 seconds for graceful shutdown
                            std::thread::sleep(Duration::from_secs(3));
                            // Check if process terminated
                            if let Ok(Some(_)) = child.try_wait() {
                                // Process already terminated
                            } else {
                                // Force kill if still running
                                let _ = child.kill();
                            }
                        }
                    }
                    #[cfg(not(unix))]
                    {
                        // Windows: just kill
                        let _ = child.kill();
                    }
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
