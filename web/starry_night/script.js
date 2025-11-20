const STAR_VERTEX_SHADER = `
    uniform float uTime;
    uniform vec2 uMouse;
    uniform float uWarpStrength;
    uniform float uAnimationSpeed;

    varying vec2 vUv;

    void main() {
        vUv = uv;

        vec3 pos = position;
        float warp = sin(pos.x * 4.0 + uTime * uAnimationSpeed) * cos(pos.y * 4.0 + uTime * 0.8 * uAnimationSpeed) * uWarpStrength;
        float mouseEffect = (pos.x * uMouse.x + pos.y * uMouse.y) * 0.15;
        pos.z += warp + mouseEffect;

        gl_Position = projectionMatrix * modelViewMatrix * vec4(pos, 1.0);
    }
`;

const STAR_FRAGMENT_SHADER = `
    uniform sampler2D uTexture;
    uniform float uTime;
    uniform vec2 uMouse;
    uniform float uFlowScale;
    uniform float uFlowStrength;
    uniform float uTwinkleStrength;
    uniform float uAnimationSpeed;

    varying vec2 vUv;

    vec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
    vec2 mod289(vec2 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
    vec3 permute(vec3 x) { return mod289(((x * 34.0) + 1.0) * x); }

    float snoise(vec2 v) {
        const vec4 C = vec4(0.211324865405187,
                            0.366025403784439,
                            -0.577350269189626,
                            0.024390243902439);
        vec2 i  = floor(v + dot(v, C.yy));
        vec2 x0 = v - i + dot(i, C.xx);
        vec2 i1 = (x0.x > x0.y) ? vec2(1.0, 0.0) : vec2(0.0, 1.0);
        vec4 x12 = x0.xyxy + C.xxzz;
        x12.xy -= i1;
        i = mod289(i);
        vec3 p = permute(permute(i.y + vec3(0.0, i1.y, 1.0))
            + i.x + vec3(0.0, i1.x, 1.0));
        vec3 m = max(0.5 - vec3(dot(x0,x0), dot(x12.xy,x12.xy), dot(x12.zw,x12.zw)), 0.0);
        m = m * m;
        m = m * m;
        vec3 x = 2.0 * fract(p * C.www) - 1.0;
        vec3 h = abs(x) - 0.5;
        vec3 ox = floor(x + 0.5);
        vec3 a0 = x - ox;
        m *= 1.79284291400159 - 0.85373472095314 * (a0 * a0 + h * h);
        vec3 g;
        g.x  = a0.x  * x0.x  + h.x  * x0.y;
        g.yz = a0.yz * x12.xz + h.yz * x12.yw;
        return 130.0 * dot(m, g);
    }

    void main() {
        vec2 uv = vUv;
        vec4 baseColor = texture2D(uTexture, uv);
        float brightness = dot(baseColor.rgb, vec3(0.299, 0.587, 0.114));

        float strength = uFlowStrength + brightness * uFlowStrength;
        float timeScale = uTime * uAnimationSpeed;

        float noiseVal = snoise(vec2(uv.x * uFlowScale, uv.y * uFlowScale + timeScale * 0.2));
        float noiseVal2 = snoise(vec2(uv.x * (uFlowScale * 1.7) - timeScale * 0.1, uv.y * (uFlowScale * 1.4)));
        vec2 flowOffset = vec2(noiseVal, noiseVal2) * strength;
        vec2 distortedUv = uv + flowOffset;

        vec4 color = texture2D(uTexture, distortedUv);

        float twinkle = 1.0 + sin(timeScale * 3.0 + uv.x * 25.0 + uv.y * 35.0) * uTwinkleStrength * brightness;
        color.rgb *= twinkle;
        color.rgb = pow(color.rgb, vec3(1.05));

        gl_FragColor = color;
    }
`;

const DEFAULT_SLIDERS = {
    blurLevel: 5,
    opacity: 0.4,
    particleCount: 2800,
    speed: 1.3,
    trailFade: 0.1,
    brightness: 1.2,
    contrast: 1.3,
    saturation: 1.4
};

const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

const valueWithStep = (input, value) => {
    if (!input) return String(value);
    const step = input.step ? Number(input.step) : NaN;
    if (!Number.isFinite(step) || step === 0) {
        return String(Math.round(value));
    }
    const decimals = (input.step.split('.')[1] || '').length;
    return Number(value).toFixed(decimals);
};

const convertBlur = (value) => value * 0.004;
const convertTwinkle = (value) => 0.05 + value * 0.3;
const convertFlowScale = (value) => value / 200;
const convertTilt = (value) => value * 3.0;

class StarryNightExperience {
    constructor() {
        this.canvas = document.getElementById('canvas');
        this.loadingEl = document.getElementById('canvas-loading');
        this.container = this.canvas ? this.canvas.parentElement : null;
        this.sidebar = document.getElementById('sidebar');

        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.mesh = null;
        this.uniforms = null;
        this.clock = null;

        this.mouse = null;
        this.targetMouse = null;
        this.targetZoom = 2.6;
        this.minZoom = 1.6;
        this.maxZoom = 5.0;

        this.sliders = {};

        this.config = {
            warpStrength: convertBlur(DEFAULT_SLIDERS.blurLevel),
            twinkleStrength: convertTwinkle(DEFAULT_SLIDERS.opacity),
            flowScale: convertFlowScale(DEFAULT_SLIDERS.particleCount),
            animationSpeed: DEFAULT_SLIDERS.speed,
            tiltStrength: convertTilt(DEFAULT_SLIDERS.trailFade),
            flowStrength: 0.015
        };

        this.init();
    }

    init() {
        if (!this.canvas || !this.container) {
            console.error('Starry Night canvas element not found.');
            return;
        }
        if (typeof THREE === 'undefined') {
            console.error('Three.js failed to load.');
            return;
        }

        this.mouse = new THREE.Vector2();
        this.targetMouse = new THREE.Vector2();
        this.clock = new THREE.Clock();
        this.initUI();
        this.initRenderer();
        this.bindPointerEvents();
        this.loadStarryNightTexture();

        const fps = document.getElementById('fps');
        if (fps) {
            fps.textContent = 'Move your mouse to tilt the canvas · Scroll to zoom';
        }
    }

    initUI() {
        this.setupSidebarToggle();
        this.setupSliders();
        this.setupButtons();
        this.applyCanvasFilters();
    }

    setupSidebarToggle() {
        const toggle = document.getElementById('sidebarToggle');
        const close = document.getElementById('sidebarClose');
        const handleToggle = () => {
            if (!this.sidebar) return;
            this.sidebar.classList.toggle('hidden');
        };
        if (toggle) toggle.addEventListener('click', handleToggle);
        if (close) close.addEventListener('click', handleToggle);
    }

    setupSliders() {
        const sliderIds = ['blurLevel', 'opacity', 'particleCount', 'speed', 'trailFade', 'brightness', 'contrast', 'saturation'];
        sliderIds.forEach((id) => {
            const input = document.getElementById(id);
            if (!input) return;
            input.dataset.defaultValue = input.value;
            this.sliders[id] = input;
        });

        const blur = this.sliders.blurLevel;
        if (blur) {
            blur.addEventListener('input', (event) => {
                const value = Number(event.target.value);
                this.config.warpStrength = convertBlur(value);
                this.updateShaderConfig();
            });
        }

        const opacity = this.sliders.opacity;
        if (opacity) {
            opacity.addEventListener('input', (event) => {
                const value = Number(event.target.value);
                this.config.twinkleStrength = convertTwinkle(value);
                this.updateShaderConfig();
            });
        }

        const particleCount = this.sliders.particleCount;
        if (particleCount) {
            particleCount.addEventListener('input', (event) => {
                const value = Number(event.target.value);
                this.config.flowScale = convertFlowScale(value);
                this.updateShaderConfig();
            });
        }

        const speed = this.sliders.speed;
        if (speed) {
            speed.addEventListener('input', (event) => {
                this.config.animationSpeed = Number(event.target.value);
                this.updateShaderConfig();
            });
        }

        const trailFade = this.sliders.trailFade;
        if (trailFade) {
            trailFade.addEventListener('input', (event) => {
                this.config.tiltStrength = convertTilt(Number(event.target.value));
            });
        }

        ['brightness', 'contrast', 'saturation'].forEach((id) => {
            const input = this.sliders[id];
            if (!input) return;
            input.addEventListener('input', () => this.applyCanvasFilters());
        });
    }

    setupButtons() {
        const randomBtn = document.getElementById('btnRandom');
        if (randomBtn) {
            randomBtn.addEventListener('click', () => this.randomizeSliders());
        }

        const resetParamsBtn = document.getElementById('btnResetParams');
        if (resetParamsBtn) {
            resetParamsBtn.addEventListener('click', () => this.resetSliders());
        }

        const resetViewBtn = document.getElementById('btnReset');
        if (resetViewBtn) {
            resetViewBtn.addEventListener('click', () => this.resetView());
        }

        const fullscreenBtn = document.getElementById('btnFullscreen');
        if (fullscreenBtn) {
            fullscreenBtn.addEventListener('click', () => this.toggleFullscreen());
        }
    }

    initRenderer() {
        this.renderer = new THREE.WebGLRenderer({ canvas: this.canvas, antialias: true, alpha: false });
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0x050505);
        this.camera = new THREE.PerspectiveCamera(45, this.getAspect(), 0.1, 100);
        this.camera.position.z = this.targetZoom;
        this.updateRendererSize();
    }

    getAspect() {
        if (!this.container) return window.innerWidth / Math.max(window.innerHeight, 1);
        return this.container.clientWidth / Math.max(this.container.clientHeight, 1);
    }

    updateRendererSize() {
        if (!this.renderer || !this.container) return;
        const width = this.container.clientWidth;
        const height = this.container.clientHeight;
        this.renderer.setSize(width, height, false);
        this.canvas.width = width;
        this.canvas.height = height;
        if (this.camera) {
            this.camera.aspect = this.getAspect();
            this.camera.updateProjectionMatrix();
        }
        if (this.uniforms) {
            this.uniforms.uResolution.value.set(width, height);
        }
    }

    bindPointerEvents() {
        if (!this.canvas) return;
        this.canvas.addEventListener('mousemove', (event) => {
            if (!this.mouse) return;
            const rect = this.canvas.getBoundingClientRect();
            const x = (event.clientX - rect.left) / rect.width;
            const y = (event.clientY - rect.top) / rect.height;
            this.mouse.set(x * 2 - 1, -(y * 2 - 1));
        });

        this.canvas.addEventListener('mouseleave', () => {
            if (!this.mouse) return;
            this.mouse.set(0, 0);
        });

        this.canvas.addEventListener('wheel', (event) => {
            event.preventDefault();
            const delta = event.deltaY * 0.0015;
            this.targetZoom = clamp(this.targetZoom + delta, this.minZoom, this.maxZoom);
        }, { passive: false });

        window.addEventListener('resize', () => this.updateRendererSize());
    }

    loadStarryNightTexture() {
        const loader = new THREE.TextureLoader();
        const sources = this.getTextureSources();
        const attemptLoad = (index) => {
            if (index >= sources.length) {
                console.error('Unable to load Starry Night texture.');
                if (this.loadingEl) this.loadingEl.textContent = 'Failed to load image';
                return;
            }
            loader.load(
                sources[index],
                (texture) => this.onTextureLoaded(texture),
                undefined,
                () => attemptLoad(index + 1)
            );
        };
        attemptLoad(0);
    }

    getTextureSources() {
        const sources = [];
        if (typeof STARRY_NIGHT_B64 !== 'undefined') {
            sources.push(STARRY_NIGHT_B64);
        }
        sources.push('starry-night.jpg');
        sources.push('https://upload.wikimedia.org/wikipedia/commons/thumb/e/ea/Van_Gogh_-_Starry_Night_-_Google_Art_Project.jpg/1280px-Van_Gogh_-_Starry_Night_-_Google_Art_Project.jpg');
        return sources;
    }

    onTextureLoaded(texture) {
        texture.colorSpace = THREE.SRGBColorSpace;
        texture.anisotropy = Math.min(8, this.renderer.capabilities.getMaxAnisotropy());

        const aspect = texture.image.width / texture.image.height;
        const planeWidth = 3.2;
        const planeHeight = planeWidth / aspect;

        const geometry = new THREE.PlaneGeometry(planeWidth, planeHeight, 160, 160);

        this.uniforms = {
            uTime: { value: 0 },
            uTexture: { value: texture },
            uMouse: { value: new THREE.Vector2(0, 0) },
            uFlowScale: { value: this.config.flowScale },
            uFlowStrength: { value: this.config.flowStrength },
            uTwinkleStrength: { value: this.config.twinkleStrength },
            uWarpStrength: { value: this.config.warpStrength },
            uAnimationSpeed: { value: this.config.animationSpeed },
            uResolution: { value: new THREE.Vector2(this.canvas.width, this.canvas.height) }
        };

        const material = new THREE.ShaderMaterial({
            vertexShader: STAR_VERTEX_SHADER,
            fragmentShader: STAR_FRAGMENT_SHADER,
            uniforms: this.uniforms,
            side: THREE.DoubleSide
        });

        this.mesh = new THREE.Mesh(geometry, material);
        this.scene.add(this.mesh);
        this.updateShaderConfig();
        this.hideLoading();
        this.animate();
    }

    animate() {
        if (!this.mesh) return;
        requestAnimationFrame(() => this.animate());
        const elapsed = this.clock.getElapsedTime();
        const damp = 0.08;

        this.uniforms.uTime.value = elapsed;
        this.targetMouse.lerp(this.mouse, 0.08);
        this.uniforms.uMouse.value.lerp(this.targetMouse, 0.2);

        this.mesh.rotation.x += (this.targetMouse.y * this.config.tiltStrength - this.mesh.rotation.x) * damp;
        this.mesh.rotation.y += (this.targetMouse.x * this.config.tiltStrength - this.mesh.rotation.y) * damp;

        this.camera.position.x += (this.targetMouse.x * 0.35 - this.camera.position.x) * 0.04;
        this.camera.position.y += (-this.targetMouse.y * 0.35 - this.camera.position.y) * 0.04;
        this.camera.position.z += (this.targetZoom - this.camera.position.z) * 0.06;
        this.camera.lookAt(this.scene.position);

        this.renderer.render(this.scene, this.camera);
    }

    updateShaderConfig() {
        if (!this.uniforms) return;
        this.uniforms.uWarpStrength.value = this.config.warpStrength;
        this.uniforms.uFlowScale.value = this.config.flowScale;
        this.uniforms.uTwinkleStrength.value = this.config.twinkleStrength;
        this.uniforms.uAnimationSpeed.value = this.config.animationSpeed;
    }

    applyCanvasFilters() {
        if (!this.canvas) return;
        const brightness = this.getSliderValue('brightness', DEFAULT_SLIDERS.brightness);
        const contrast = this.getSliderValue('contrast', DEFAULT_SLIDERS.contrast);
        const saturation = this.getSliderValue('saturation', DEFAULT_SLIDERS.saturation);
        this.canvas.style.filter = `brightness(${brightness}) contrast(${contrast}) saturate(${saturation})`;
    }

    getSliderValue(id, fallback) {
        const slider = this.sliders[id];
        if (!slider) return fallback;
        const parsed = Number(slider.value);
        return Number.isFinite(parsed) ? parsed : fallback;
    }

    randomizeSliders() {
        Object.values(this.sliders).forEach((slider) => {
            if (!slider) return;
            const min = Number(slider.min || slider.getAttribute('min') || 0);
            const max = Number(slider.max || slider.getAttribute('max') || 1);
            const randomValue = Math.random() * (max - min) + min;
            slider.value = valueWithStep(slider, randomValue);
            slider.dispatchEvent(new Event('input'));
        });
        this.applyCanvasFilters();
    }

    resetSliders() {
        Object.values(this.sliders).forEach((slider) => {
            if (!slider) return;
            const defaultValue = slider.dataset.defaultValue;
            if (typeof defaultValue === 'undefined') return;
            slider.value = defaultValue;
            slider.dispatchEvent(new Event('input'));
        });
        this.applyCanvasFilters();
    }

    resetView() {
        if (this.mouse) this.mouse.set(0, 0);
        if (this.targetMouse) this.targetMouse.set(0, 0);
        this.targetZoom = 2.6;
        if (this.mesh) {
            this.mesh.rotation.set(0, 0, 0);
        }
    }

    toggleFullscreen() {
        const container = document.querySelector('.canvas-container');
        if (!container) return;
        if (!document.fullscreenElement) {
            container.requestFullscreen?.();
        } else {
            document.exitFullscreen?.();
        }
    }

    hideLoading() {
        if (!this.loadingEl) return;
        this.loadingEl.style.opacity = '0';
        setTimeout(() => {
            if (this.loadingEl) {
                this.loadingEl.style.display = 'none';
            }
        }, 600);
    }
}

const startExperience = () => {
    if (typeof THREE === 'undefined') {
        window.addEventListener('load', () => new StarryNightExperience());
        return;
    }
    new StarryNightExperience();
};

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', startExperience);
} else {
    startExperience();
}
