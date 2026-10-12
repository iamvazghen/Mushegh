import { useEffect, useState } from 'react';
import { Canvas } from '@react-three/fiber';
import { Bounds, Edges, Grid, OrbitControls } from '@react-three/drei';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { LoadingManager, type Group, type Mesh, type Material, Texture } from 'three';
import { Upload } from 'lucide-react';
import { CanvasLoader, Empty } from '../components';

export interface PrimitiveSpec { primitive: 'box' | 'sphere' | 'cylinder' | 'cone' | 'torus'; color?: string }

function Primitive({ spec, edge }: { spec: PrimitiveSpec; edge: string }) {
  const geometry = spec.primitive === 'sphere' ? <sphereGeometry args={[1.2, 48, 32]}/> :
    spec.primitive === 'cylinder' ? <cylinderGeometry args={[0.9, 0.9, 2.1, 48]}/> :
    spec.primitive === 'cone' ? <coneGeometry args={[1.1, 2.2, 48]}/> :
    spec.primitive === 'torus' ? <torusGeometry args={[1.05, 0.36, 24, 64]}/> : <boxGeometry args={[1.8, 1.8, 1.8]}/>;
  return <mesh>{geometry}<meshStandardMaterial color={spec.color || edge} roughness={0.34} metalness={0.35}/><Edges color={edge}/></mesh>;
}

function disposeModel(model: Group) {
  model.traverse(o => { const m = o as Mesh; m.geometry?.dispose(); const mats = m.material ? (Array.isArray(m.material) ? m.material : [m.material]) : []; mats.forEach((mat: Material) => { Object.values(mat).forEach(v => { if (v instanceof Texture) v.dispose(); }); mat.dispose(); }); });
}
export default function ModelCanvas({ active, reduced, instruction }: { active: boolean; reduced: boolean; instruction: PrimitiveSpec | null }) {
  const [file, setFile] = useState<File | null>(null), [model, setModel] = useState<Group | null>(null);
  const [error, setError] = useState(''), [loading, setLoading] = useState(false);
  const [info, setInfo] = useState({ meshes: 0, vertices: 0 });
  const colors = getComputedStyle(document.documentElement);
  const cyan = colors.getPropertyValue('--color-accent').trim();
  const grid = colors.getPropertyValue('--color-line').trim();
  useEffect(() => {
    if (!file) return;
    let cancelled = false, loaded: Group | null = null;
    setLoading(true); setError(''); setModel(null);
    // A local GLB may only reference embedded resources. Do not follow embedded external URLs.
    const manager = new LoadingManager();
    manager.setURLModifier(url => { if (/^(blob:|data:)/i.test(url)) return url; throw new Error('External asset references are not supported'); });
    file.arrayBuffer().then(buffer => new GLTFLoader(manager).parseAsync(buffer, '')).then(gltf => {
      loaded = gltf.scene;
      if (cancelled) { disposeModel(loaded); loaded = null; return; }
      let meshes = 0, vertices = 0;
      loaded.traverse(o => { const m = o as Mesh; if (m.isMesh) { meshes++; vertices += m.geometry.attributes.position?.count || 0; } });
      setInfo({ meshes, vertices }); setModel(loaded); setLoading(false);
    }).catch(() => { if (!cancelled) { setError('Could not load this model. Choose a self-contained GLB (under 50 MB).'); setLoading(false); } });
    return () => { cancelled = true; if (loaded) disposeModel(loaded); };
  }, [file]);
  const scene = model || instruction;
  const displayedInfo = model ? info : instruction ? { meshes: 1, vertices: 0 } : { meshes: 0, vertices: 0 };
  return <div className="model-view"><div className="model-tools"><span className="mono">{file?.name || instruction?.primitive.toUpperCase() || 'SCENE EMPTY'}</span><label className="icon-button" title="Open local GLB"><Upload size={16}/><span className="sr-only">Open local GLB</span><input type="file" accept=".glb" onChange={e => { const f = e.target.files?.[0]; if (f && f.size <= 50 * 1024 * 1024) setFile(f); else if (f) setError('Choose a GLB smaller than 50 MB.'); }} /></label></div>
    <div className="model-render">{!scene ? <Empty title="Scene ready for Mushegh" icon="box"><p>Ask Mushegh to render a box, sphere, cylinder, cone, or torus—or open a local GLB.</p></Empty> : active && <Canvas aria-label={`Interactive 3D ${file?.name || instruction?.primitive || 'model'} scene`} frameloop="demand" dpr={[1, 1.5]} camera={{ position: [4, 3, 5], fov: 38 }} gl={{ antialias: true, powerPreference: 'low-power' }} fallback={<p className="footnote">WebGL is unavailable in this browser.</p>}><ambientLight intensity={1.2}/><directionalLight position={[5, 8, 3]} intensity={2}/><Bounds fit clip observe margin={1.5} maxDuration={reduced ? 0 : 1}>{model ? <primitive object={model}/> : instruction ? <Primitive spec={instruction} edge={cyan}/> : null}</Bounds><Grid position={[0, -1.3, 0]} args={[12, 12]} cellSize={0.5} cellColor={grid} sectionColor={cyan} sectionSize={2} fadeDistance={18} infiniteGrid/><OrbitControls makeDefault enableDamping={!reduced} autoRotate={false}/></Canvas>}</div>
    {loading && <div className="model-loading"><CanvasLoader label="Parsing local GLB" detail="Reading embedded meshes and materials"/></div>}{error && <p role="alert" className="model-error error">{error}</p>}
    {scene && <div className="model-footer"><div><span className="mono accent">{displayedInfo.meshes} MESH{displayedInfo.meshes === 1 ? '' : 'ES'}</span><span className="mono muted">{displayedInfo.vertices ? `${displayedInfo.vertices.toLocaleString()} VERTICES` : 'PROCEDURAL GEOMETRY'}</span></div><p>Drag to orbit · Scroll to zoom</p></div>}
  </div>;
}
