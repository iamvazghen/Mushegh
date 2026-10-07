import { useEffect, useRef, useState } from 'react';
import { Howl } from 'howler';
import { Pause, Play, Upload, Volume2 } from 'lucide-react';
import { CanvasLoader, Empty } from '../components';
export default function AudioCanvas() {
  const sound = useRef<Howl | null>(null); const url = useRef('');
  const [name, setName] = useState(''), [playing, setPlaying] = useState(false), [volume, setVolume] = useState(0.4), [error, setError] = useState(''), [loading, setLoading] = useState(false);
  useEffect(() => () => { sound.current?.unload(); if (url.current) URL.revokeObjectURL(url.current); }, []);
  function open(file: File) {
    sound.current?.unload(); if (url.current) URL.revokeObjectURL(url.current);
    url.current = URL.createObjectURL(file); setName(file.name); setPlaying(false); setError(''); setLoading(true);
    sound.current = new Howl({ src: [url.current], format: [file.name.split('.').pop() || 'mp3'], html5: true, volume,
      onload: () => setLoading(false), onplay: () => setPlaying(true), onpause: () => setPlaying(false), onend: () => setPlaying(false),
      onloaderror: () => { setLoading(false); setError('This audio file could not be loaded.'); }, onplayerror: () => { setLoading(false); setPlaying(false); setError('Playback failed. Try a supported MP3 or WAV file.'); } });
  }
  return <div className="canvas-scroll"><label className="file-button"><Upload size={16}/>Open audio<input type="file" accept="audio/*" onChange={e => { if (e.target.files?.[0]) open(e.target.files[0]); }}/></label>
    {!name ? <Empty title="Make room for focus" icon="audio"><p>Choose an ambient track from your device. Playback continues when this canvas is in the background; dismissing it stops playback.</p></Empty> : <div className="audio-player"><span className="mono accent">LOCAL AUDIO</span><h3>{name}</h3><button className="play-button" aria-label={playing ? 'Pause audio' : 'Play audio'} onClick={() => { if (playing) sound.current?.pause(); else sound.current?.play(); }}>{playing ? <Pause/> : <Play/>}</button><label className="volume"><Volume2 size={18}/><span className="sr-only">Volume</span><input type="range" min="0" max="1" step="0.01" value={volume} onChange={e => { const v = Number(e.target.value); setVolume(v); sound.current?.volume(v); }}/><span className="mono">{Math.round(volume * 100)}%</span></label></div>}
    {loading && <CanvasLoader compact label="Preparing local audio" detail="Decoding the selected track"/>}
    {error && <p role="alert" className="error">{error}</p>}
  </div>;
}
