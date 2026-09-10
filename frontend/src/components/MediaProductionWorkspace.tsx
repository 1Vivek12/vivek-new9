import { useState, useEffect } from 'react';

interface Story {
  id: string;
  title: string;
}

interface MediaAsset {
  id: string;
  story_id: string | null;
  filename: string;
  original_filename: string;
  media_type: string;
  mime_type: string;
  file_size: number;
  duration: number | null;
  width: number | null;
  height: number | null;
  codec: string | null;
  container: string | null;
  checksum: string;
  status: string;
  rights_metadata: {
    rights_type: string;
    license_details?: string;
    attribution?: string;
    reuse_permitted?: boolean;
  };
  created_at: string;
}

interface TranscriptSegment {
  id: string;
  sequence: number;
  start_time: number;
  end_time: number;
  text: string;
  speaker_label: string;
  confidence: number;
}

interface Transcript {
  id: string;
  language: string;
  model_provider: string;
  duration: number;
  status: string;
  full_text: string;
  confidence_score: number;
  segments: TranscriptSegment[];
}

interface Scene {
  id: string;
  sequence: number;
  start_time: number;
  end_time: number;
  scene_label: string;
  confidence: number;
}

interface OCRItem {
  id: string;
  timestamp: number;
  extracted_text: string;
  confidence: number;
}

interface ClipCandidate {
  id: string;
  title: string;
  start_time: number;
  end_time: number;
  duration: number;
  category: string;
  reason: string;
  suggested_aspect_ratio: string;
  confidence: number;
  status: string;
  rejection_reason: string | null;
}

interface SubtitleTrack {
  id: string;
  language: string;
  format: string;
  content: string;
  status: string;
  generated_by: string;
}

interface MediaDerivative {
  id: string;
  derivative_type: string;
  mime_type: string;
  file_size: number;
  processing_status: string;
}

interface VisualAsset {
  id: string;
  asset_type: string;
  headline_text: string | null;
  visual_concept_description: string;
  status: string;
  rejection_reason: string | null;
}

interface ProcessingJob {
  id: string;
  job_type: string;
  status: string;
  attempts: number;
  safe_error_message: string | null;
}

export const MediaProductionWorkspace = () => {
  const [stories, setStories] = useState<Story[]>([]);
  const [mediaList, setMediaList] = useState<MediaAsset[]>([]);
  const [selectedAssetId, setSelectedAssetId] = useState<string | null>(null);

  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<'transcript' | 'subtitles' | 'scenes' | 'ocr' | 'clips' | 'derivatives' | 'visuals' | 'jobs'>('transcript');

  const [transcript, setTranscript] = useState<Transcript | null>(null);
  const [scenes, setScenes] = useState<Scene[]>([]);
  const [ocrList, setOcrList] = useState<OCRItem[]>([]);
  const [clips, setClips] = useState<ClipCandidate[]>([]);
  const [subtitles, setSubtitles] = useState<SubtitleTrack[]>([]);
  const [derivatives, setDerivatives] = useState<MediaDerivative[]>([]);
  const [visuals, setVisuals] = useState<VisualAsset[]>([]);
  const [jobs, setJobs] = useState<ProcessingJob[]>([]);

  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [selectedStoryId, setSelectedStoryId] = useState<string>('');
  const [rightsType, setRightsType] = useState('OWNED');
  const [licenseDetails, setLicenseDetails] = useState('');
  const [attribution, setAttribution] = useState('');
  const [reusePermitted, setReusePermitted] = useState(true);
  const [uploading, setUploading] = useState(false);

  const [rejectionTarget, setRejectionTarget] = useState<{ type: 'clip' | 'visual'; id: string } | null>(null);
  const [rejectionReason, setRejectionReason] = useState('');

  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const tenantHeaders = {
    'X-Tenant-ID': 'tenant-news9',
    'X-User-Role': 'EDITOR',
    'X-User-ID': 'user-news9-editor',
  };

  const fetchStories = async () => {
    try {
      const res = await fetch('/api/v1/stories', { headers: tenantHeaders });
      if (res.ok) setStories(await res.json());
    } catch {
      // Offline fallback
    }
  };

  const fetchMediaList = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/v1/media', { headers: tenantHeaders });
      if (res.ok) {
        const data = await res.json();
        setMediaList(data);
        if (data.length > 0 && !selectedAssetId) {
          setSelectedAssetId(data[0].id);
        }
      }
    } catch {
      // Offline fallback
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStories();
    fetchMediaList();
  }, []);

  const loadAssetDetails = async (assetId: string) => {
    setErrorMsg(null);
    setSuccessMsg(null);

    try {
      // 1. Transcript
      const txRes = await fetch(`/api/v1/media/${assetId}/transcript`, { headers: tenantHeaders });
      if (txRes.ok) setTranscript(await txRes.json());
      else setTranscript(null);

      // 2. Scenes
      const scRes = await fetch(`/api/v1/media/${assetId}/scenes`, { headers: tenantHeaders });
      if (scRes.ok) setScenes(await scRes.json());
      else setScenes([]);

      // 3. OCR
      const ocrRes = await fetch(`/api/v1/media/${assetId}/ocr`, { headers: tenantHeaders });
      if (ocrRes.ok) setOcrList(await ocrRes.json());
      else setOcrList([]);

      // 4. Clips
      const clRes = await fetch(`/api/v1/media/${assetId}/moments`, { headers: tenantHeaders });
      if (clRes.ok) setClips(await clRes.json());
      else setClips([]);

      // 5. Subtitles
      const subRes = await fetch(`/api/v1/media/${assetId}/subtitles`, { headers: tenantHeaders });
      if (subRes.ok) setSubtitles(await subRes.json());
      else setSubtitles([]);

      // 6. Derivatives
      const derRes = await fetch(`/api/v1/media/${assetId}/derivatives`, { headers: tenantHeaders });
      if (derRes.ok) setDerivatives(await derRes.json());
      else setDerivatives([]);

      // 7. Visuals
      const visRes = await fetch(`/api/v1/media/${assetId}/visual-assets`, { headers: tenantHeaders });
      if (visRes.ok) setVisuals(await visRes.json());
      else setVisuals([]);

      // 8. Jobs
      const jbRes = await fetch(`/api/v1/media/${assetId}/jobs`, { headers: tenantHeaders });
      if (jbRes.ok) setJobs(await jbRes.json());
      else setJobs([]);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Error loading details');
    }
  };

  useEffect(() => {
    if (selectedAssetId) {
      loadAssetDetails(selectedAssetId);
    }
  }, [selectedAssetId]);

  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) {
      setErrorMsg('Please select a media file to upload.');
      return;
    }

    setUploading(true);
    setErrorMsg(null);
    const formData = new FormData();
    formData.append('file', selectedFile);
    if (selectedStoryId) formData.append('story_id', selectedStoryId);
    formData.append('rights_type', rightsType);
    if (licenseDetails) formData.append('license_details', licenseDetails);
    if (attribution) formData.append('attribution', attribution);
    formData.append('reuse_permitted', String(reusePermitted));

    try {
      const res = await fetch('/api/v1/media/upload', {
        method: 'POST',
        headers: tenantHeaders,
        body: formData,
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Upload failed');
      }

      const created = await res.json();
      setSuccessMsg(`Media uploaded successfully: ${created.original_filename}`);
      setUploadModalOpen(false);
      setSelectedFile(null);
      await fetchMediaList();
      setSelectedAssetId(created.id);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const handleProcessMedia = async () => {
    if (!selectedAssetId) return;
    setLoading(true);
    setErrorMsg(null);
    setSuccessMsg(null);

    try {
      const res = await fetch(`/api/v1/media/${selectedAssetId}/process`, {
        method: 'POST',
        headers: tenantHeaders,
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Processing failed');
      }
      setSuccessMsg(`Media processing completed. Status: ${data.status}`);
      await fetchMediaList();
      await loadAssetDetails(selectedAssetId);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Processing error');
    } finally {
      setLoading(false);
    }
  };

  const handleValidateMedia = async () => {
    if (!selectedAssetId) return;
    try {
      const res = await fetch(`/api/v1/media/${selectedAssetId}/validate`, {
        method: 'POST',
        headers: tenantHeaders,
      });
      const data = await res.json();
      if (res.ok) {
        setSuccessMsg(`Validation verified. Status: ${data.status}`);
        await fetchMediaList();
      } else {
        setErrorMsg(data.detail || 'Validation failed');
      }
    } catch {
      setErrorMsg('Validation request error');
    }
  };

  const handleReviewAction = async (type: 'clip' | 'visual', id: string, action: 'ACCEPT' | 'REJECT') => {
    if (action === 'REJECT') {
      setRejectionTarget({ type, id });
      setRejectionReason('');
      return;
    }

    await submitReview(type, id, 'ACCEPT', null);
  };

  const submitReview = async (type: 'clip' | 'visual', id: string, action: 'ACCEPT' | 'REJECT', reason: string | null) => {
    setErrorMsg(null);
    const endpoint = type === 'clip' ? `/api/v1/media/moments/${id}/review` : `/api/v1/media/visual-assets/${id}/review`;

    try {
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { ...tenantHeaders, 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, rejection_reason: reason }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Review action failed');
      }
      setSuccessMsg(`${type === 'clip' ? 'Clip candidate' : 'Thumbnail'} marked as ${action}ED`);
      setRejectionTarget(null);
      if (selectedAssetId) await loadAssetDetails(selectedAssetId);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Action failed');
    }
  };

  const selectedAsset = mediaList.find((m) => m.id === selectedAssetId);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Header & Primary Controls */}
      <div className="card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2>🎬 Media &amp; Video Production Workspace</h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
            Transform authorized footage, transcripts, and scene analysis into production-ready news assets.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.75rem' }}>
          <button
            onClick={() => setUploadModalOpen(true)}
            style={{
              padding: '0.6rem 1.2rem',
              backgroundColor: 'var(--accent-red)',
              color: '#fff',
              border: 'none',
              borderRadius: '4px',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            + Upload Raw Media
          </button>
        </div>
      </div>

      {errorMsg && (
        <div style={{ padding: '0.75rem 1rem', backgroundColor: '#fee2e2', color: '#b91c1c', borderRadius: '4px', borderLeft: '4px solid #ef4444' }}>
          <strong>Error:</strong> {errorMsg}
        </div>
      )}
      {successMsg && (
        <div style={{ padding: '0.75rem 1rem', backgroundColor: '#dcfce7', color: '#15803d', borderRadius: '4px', borderLeft: '4px solid #22c55e' }}>
          <strong>Success:</strong> {successMsg}
        </div>
      )}

      {/* Main Grid: Asset Library vs Detail Studio */}
      <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: '1.5rem', alignItems: 'start' }}>
        {/* Left: Media Library List */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3 style={{ fontSize: '1.1rem' }}>Media Assets ({mediaList.length})</h3>
            <button onClick={fetchMediaList} style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer' }}>🔄</button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', maxHeight: '650px', overflowY: 'auto' }}>
            {mediaList.length === 0 ? (
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>No media assets uploaded yet.</p>
            ) : (
              mediaList.map((asset) => {
                const isSelected = asset.id === selectedAssetId;
                return (
                  <div
                    key={asset.id}
                    onClick={() => setSelectedAssetId(asset.id)}
                    style={{
                      padding: '0.75rem',
                      borderRadius: '6px',
                      border: isSelected ? '2px solid var(--accent-red)' : '1px solid var(--border-color)',
                      backgroundColor: isSelected ? 'rgba(239, 68, 68, 0.05)' : 'transparent',
                      cursor: 'pointer',
                    }}
                  >
                    <div style={{ fontWeight: 600, fontSize: '0.9rem', marginBottom: '0.25rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {asset.original_filename}
                    </div>
                    <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap', marginBottom: '0.4rem' }}>
                      <span className={`badge ${asset.status === 'READY' ? 'badge-green' : asset.status === 'FAILED' ? 'badge-red' : 'badge-yellow'}`}>
                        {asset.status}
                      </span>
                      <span className="badge" style={{ backgroundColor: '#f1f5f9', color: '#475569' }}>
                        {asset.media_type}
                      </span>
                      <span
                        className="badge"
                        style={{
                          backgroundColor: asset.rights_metadata?.rights_type === 'RESTRICTED' ? '#fee2e2' : '#e0f2fe',
                          color: asset.rights_metadata?.rights_type === 'RESTRICTED' ? '#991b1b' : '#0369a1',
                        }}
                      >
                        {asset.rights_metadata?.rights_type || 'UNKNOWN'}
                      </span>
                    </div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                      {(asset.file_size / (1024 * 1024)).toFixed(2)} MB &middot; {new Date(asset.created_at).toLocaleDateString()}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Right: Media Studio Inspector */}
        {selectedAsset ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            {/* Top Info Banner */}
            <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                  <h3 style={{ fontSize: '1.2rem', marginBottom: '0.25rem' }}>{selectedAsset.original_filename}</h3>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', fontFamily: 'monospace' }}>
                    SHA-256: {selectedAsset.checksum}
                  </div>
                </div>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  <button
                    onClick={handleValidateMedia}
                    style={{ padding: '0.4rem 0.8rem', backgroundColor: '#f1f5f9', border: '1px solid #cbd5e1', borderRadius: '4px', cursor: 'pointer', fontSize: '0.85rem' }}
                  >
                    🔍 Verify Integrity
                  </button>
                  <button
                    onClick={handleProcessMedia}
                    disabled={loading}
                    style={{
                      padding: '0.4rem 0.9rem',
                      backgroundColor: 'var(--accent-red)',
                      color: '#fff',
                      border: 'none',
                      borderRadius: '4px',
                      cursor: 'pointer',
                      fontSize: '0.85rem',
                      fontWeight: 600,
                    }}
                  >
                    ⚡ Run Pipeline
                  </button>
                  <a
                    href={`/api/v1/media/${selectedAsset.id}/download`}
                    target="_blank"
                    rel="noreferrer"
                    style={{
                      padding: '0.4rem 0.8rem',
                      backgroundColor: '#f1f5f9',
                      border: '1px solid #cbd5e1',
                      borderRadius: '4px',
                      color: 'inherit',
                      textDecoration: 'none',
                      fontSize: '0.85rem',
                    }}
                  >
                    ⬇️ Download
                  </a>
                </div>
              </div>

              {/* Technical Metadata Grid */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '0.75rem', backgroundColor: '#f8fafc', padding: '0.75rem', borderRadius: '6px', fontSize: '0.8rem' }}>
                <div>
                  <span style={{ color: 'var(--text-secondary)' }}>Dimensions:</span>
                  <div style={{ fontWeight: 600 }}>{selectedAsset.width && selectedAsset.height ? `${selectedAsset.width}x${selectedAsset.height}` : 'N/A'}</div>
                </div>
                <div>
                  <span style={{ color: 'var(--text-secondary)' }}>Duration:</span>
                  <div style={{ fontWeight: 600 }}>{selectedAsset.duration ? `${selectedAsset.duration.toFixed(1)}s` : 'N/A'}</div>
                </div>
                <div>
                  <span style={{ color: 'var(--text-secondary)' }}>Codec / Container:</span>
                  <div style={{ fontWeight: 600 }}>{selectedAsset.codec || 'N/A'} ({selectedAsset.container || 'N/A'})</div>
                </div>
                <div>
                  <span style={{ color: 'var(--text-secondary)' }}>MIME Type:</span>
                  <div style={{ fontWeight: 600 }}>{selectedAsset.mime_type}</div>
                </div>
                <div>
                  <span style={{ color: 'var(--text-secondary)' }}>Rights Status:</span>
                  <div style={{ fontWeight: 600, color: selectedAsset.rights_metadata?.rights_type === 'RESTRICTED' ? '#b91c1c' : '#15803d' }}>
                    {selectedAsset.rights_metadata?.rights_type || 'UNKNOWN'}
                  </div>
                </div>
              </div>
            </div>

            {/* Studio Navigation Tabs */}
            <div style={{ display: 'flex', gap: '0.5rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem' }}>
              {[
                { id: 'transcript', label: '📝 Transcript' },
                { id: 'subtitles', label: '💬 Subtitles (SRT/VTT)' },
                { id: 'scenes', label: '🎬 Scene Cuts' },
                { id: 'ocr', label: '🔍 OCR Text' },
                { id: 'clips', label: '✨ Clip Moments' },
                { id: 'derivatives', label: '📦 Derivatives' },
                { id: 'visuals', label: '🖼️ Thumbnails' },
                { id: 'jobs', label: '⚙️ Pipeline Jobs' },
              ].map((t) => (
                <button
                  key={t.id}
                  onClick={() => setActiveTab(t.id as any)}
                  style={{
                    background: 'none',
                    border: 'none',
                    borderBottom: activeTab === t.id ? '2px solid var(--accent-red)' : 'none',
                    color: activeTab === t.id ? 'var(--text-primary)' : 'var(--text-secondary)',
                    fontWeight: activeTab === t.id ? 700 : 500,
                    padding: '0.5rem 0.75rem',
                    cursor: 'pointer',
                    fontSize: '0.9rem',
                  }}
                >
                  {t.label}
                </button>
              ))}
            </div>

            {/* Studio Tab Content */}
            <div className="card">
              {/* Transcript Tab */}
              {activeTab === 'transcript' && (
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1rem' }}>
                    <h4>Local Whisper Transcription</h4>
                    {transcript && <span className="badge badge-green">Engine: {transcript.model_provider}</span>}
                  </div>
                  {!transcript ? (
                    <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>No transcript available. Run pipeline to transcribe audio.</p>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                      <div style={{ padding: '0.75rem', backgroundColor: '#f8fafc', borderRadius: '4px', fontSize: '0.9rem', fontStyle: 'italic', color: '#334155' }}>
                        "{transcript.full_text}"
                      </div>
                      <div style={{ marginTop: '0.5rem' }}>
                        <h5 style={{ marginBottom: '0.5rem' }}>Dialogue Segments ({transcript.segments?.length || 0})</h5>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', maxHeight: '350px', overflowY: 'auto' }}>
                          {transcript.segments?.map((seg) => (
                            <div key={seg.id} style={{ padding: '0.5rem 0.75rem', border: '1px solid #e2e8f0', borderRadius: '4px', fontSize: '0.85rem' }}>
                              <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-secondary)', fontSize: '0.75rem', marginBottom: '0.2rem' }}>
                                <span style={{ fontWeight: 600, color: 'var(--accent-red)' }}>{seg.speaker_label}</span>
                                <span>{seg.start_time.toFixed(1)}s - {seg.end_time.toFixed(1)}s</span>
                              </div>
                              <div>{seg.text}</div>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Subtitles Tab */}
              {activeTab === 'subtitles' && (
                <div>
                  <h4 style={{ marginBottom: '1rem' }}>Timed Subtitle Tracks (SRT &amp; WebVTT)</h4>
                  {subtitles.length === 0 ? (
                    <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>No subtitle tracks generated yet.</p>
                  ) : (
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                      {subtitles.map((sub) => (
                        <div key={sub.id} style={{ border: '1px solid var(--border-color)', borderRadius: '6px', padding: '0.75rem' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                            <span className="badge badge-green">{sub.format} Track</span>
                            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>{sub.language}</span>
                          </div>
                          <pre style={{ backgroundColor: '#f8fafc', padding: '0.5rem', borderRadius: '4px', fontSize: '0.75rem', maxHeight: '250px', overflowY: 'auto' }}>
                            {sub.content}
                          </pre>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Scenes Tab */}
              {activeTab === 'scenes' && (
                <div>
                  <h4 style={{ marginBottom: '1rem' }}>Detected Visual Shot Boundaries</h4>
                  {scenes.length === 0 ? (
                    <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>No visual scene transitions detected.</p>
                  ) : (
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '0.75rem' }}>
                      {scenes.map((s) => (
                        <div key={s.id} style={{ border: '1px solid var(--border-color)', borderRadius: '6px', padding: '0.75rem' }}>
                          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Shot #{s.sequence}</div>
                          <div style={{ fontWeight: 600, margin: '0.25rem 0' }}>{s.scene_label}</div>
                          <div style={{ fontSize: '0.75rem', color: '#64748b' }}>
                            {s.start_time.toFixed(1)}s &rarr; {s.end_time.toFixed(1)}s
                          </div>
                          <span className="badge badge-green" style={{ marginTop: '0.4rem' }}>{(s.confidence * 100).toFixed(0)}% confidence</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* OCR Tab */}
              {activeTab === 'ocr' && (
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1rem' }}>
                    <h4>On-Screen OCR Text Extraction</h4>
                    <span className="badge" style={{ backgroundColor: '#f1f5f9', color: '#64748b' }}>MACHINE GENERATED (UNVERIFIED)</span>
                  </div>
                  {ocrList.length === 0 ? (
                    <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>No on-screen OCR text extracted.</p>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                      {ocrList.map((item) => (
                        <div key={item.id} style={{ padding: '0.5rem 0.75rem', border: '1px solid #e2e8f0', borderRadius: '4px', fontSize: '0.85rem', display: 'flex', justifyContent: 'space-between' }}>
                          <div>
                            <span style={{ fontWeight: 600, color: '#334155' }}>[{item.timestamp.toFixed(1)}s]: </span>
                            <span>{item.extracted_text}</span>
                          </div>
                          <span className="badge badge-green">{(item.confidence * 100).toFixed(0)}%</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Clip Candidates Tab */}
              {activeTab === 'clips' && (
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1rem' }}>
                    <h4>Important Moments &amp; Clip Suggestions</h4>
                    <span className="badge" style={{ backgroundColor: '#fef3c7', color: '#92400e' }}>AI ADVISORY &middot; HUMAN REVIEW REQUIRED</span>
                  </div>
                  {clips.length === 0 ? (
                    <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>No clip candidates identified.</p>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                      {clips.map((clip) => (
                        <div
                          key={clip.id}
                          style={{
                            border: '1px solid var(--border-color)',
                            borderRadius: '6px',
                            padding: '0.75rem',
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                          }}
                        >
                          <div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
                              <span style={{ fontWeight: 600 }}>{clip.title}</span>
                              <span className="badge badge-green">{clip.category}</span>
                              <span className="badge" style={{ backgroundColor: '#f1f5f9', color: '#475569' }}>{clip.suggested_aspect_ratio}</span>
                            </div>
                            <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', margin: '0.2rem 0' }}>{clip.reason}</p>
                            <div style={{ fontSize: '0.75rem', color: '#64748b' }}>
                              {clip.start_time.toFixed(1)}s &rarr; {clip.end_time.toFixed(1)}s ({clip.duration.toFixed(1)}s)
                            </div>
                            {clip.rejection_reason && (
                              <div style={{ fontSize: '0.75rem', color: '#b91c1c', marginTop: '0.25rem' }}>
                                <strong>Rejection Reason:</strong> {clip.rejection_reason}
                              </div>
                            )}
                          </div>
                          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                            <span className={`badge ${clip.status === 'ACCEPTED' ? 'badge-green' : clip.status === 'REJECTED' ? 'badge-red' : 'badge-yellow'}`}>
                              {clip.status}
                            </span>
                            {clip.status === 'SUGGESTED' && (
                              <>
                                <button
                                  onClick={() => handleReviewAction('clip', clip.id, 'ACCEPT')}
                                  style={{ padding: '0.35rem 0.7rem', backgroundColor: '#22c55e', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '0.8rem' }}
                                >
                                  Accept
                                </button>
                                <button
                                  onClick={() => handleReviewAction('clip', clip.id, 'REJECT')}
                                  style={{ padding: '0.35rem 0.7rem', backgroundColor: '#ef4444', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '0.8rem' }}
                                >
                                  Reject
                                </button>
                              </>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Derivatives Tab */}
              {activeTab === 'derivatives' && (
                <div>
                  <h4 style={{ marginBottom: '1rem' }}>Generated Media Derivatives</h4>
                  {derivatives.length === 0 ? (
                    <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>No derivatives generated.</p>
                  ) : (
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '0.75rem' }}>
                      {derivatives.map((d) => (
                        <div key={d.id} style={{ border: '1px solid var(--border-color)', borderRadius: '6px', padding: '0.75rem' }}>
                          <span className="badge badge-green" style={{ marginBottom: '0.4rem' }}>{d.derivative_type}</span>
                          <div style={{ fontSize: '0.8rem', margin: '0.2rem 0' }}>Format: {d.mime_type}</div>
                          <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Size: {(d.file_size / (1024 * 1024)).toFixed(2)} MB</div>
                          <div style={{ marginTop: '0.5rem', fontSize: '0.8rem' }}>Status: <strong>{d.processing_status}</strong></div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Visuals / Thumbnails Tab */}
              {activeTab === 'visuals' && (
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1rem' }}>
                    <h4>Thumbnail Concepts &amp; Keyframe Cards</h4>
                    <span className="badge" style={{ backgroundColor: '#fef3c7', color: '#92400e' }}>EDITORIAL REVIEW REQUIRED</span>
                  </div>
                  {visuals.length === 0 ? (
                    <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>No visual assets found.</p>
                  ) : (
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                      {visuals.map((vis) => (
                        <div key={vis.id} style={{ border: '1px solid var(--border-color)', borderRadius: '6px', padding: '0.75rem' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.4rem' }}>
                            <span className="badge badge-green">{vis.asset_type}</span>
                            <span className={`badge ${vis.status === 'ACCEPTED' ? 'badge-green' : vis.status === 'REJECTED' ? 'badge-red' : 'badge-yellow'}`}>
                              {vis.status}
                            </span>
                          </div>
                          {vis.headline_text && <div style={{ fontWeight: 600, fontSize: '0.9rem', marginBottom: '0.3rem' }}>{vis.headline_text}</div>}
                          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', fontStyle: 'italic' }}>{vis.visual_concept_description}</p>
                          {vis.status === 'CANDIDATE' && (
                            <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.75rem' }}>
                              <button
                                onClick={() => handleReviewAction('visual', vis.id, 'ACCEPT')}
                                style={{ padding: '0.35rem 0.7rem', backgroundColor: '#22c55e', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '0.8rem' }}
                              >
                                Accept Concept
                              </button>
                              <button
                                onClick={() => handleReviewAction('visual', vis.id, 'REJECT')}
                                style={{ padding: '0.35rem 0.7rem', backgroundColor: '#ef4444', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '0.8rem' }}
                              >
                                Reject Concept
                              </button>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Jobs Tab */}
              {activeTab === 'jobs' && (
                <div>
                  <h4 style={{ marginBottom: '1rem' }}>Pipeline Processing Tasks</h4>
                  {jobs.length === 0 ? (
                    <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>No processing jobs logged for this media.</p>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                      {jobs.map((j) => (
                        <div key={j.id} style={{ padding: '0.6rem 0.8rem', border: '1px solid #e2e8f0', borderRadius: '4px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <div>
                            <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>{j.job_type}</span>
                            {j.safe_error_message && (
                              <div style={{ color: '#b91c1c', fontSize: '0.8rem', marginTop: '0.2rem' }}>
                                Error: {j.safe_error_message}
                              </div>
                            )}
                          </div>
                          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Attempts: {j.attempts}</span>
                            <span className={`badge ${j.status === 'COMPLETED' ? 'badge-green' : j.status === 'FAILED' ? 'badge-red' : 'badge-yellow'}`}>
                              {j.status}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="card" style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '300px', color: 'var(--text-secondary)' }}>
            Select or upload a media asset to view production controls.
          </div>
        )}
      </div>

      {/* Upload Modal */}
      {uploadModalOpen && (
        <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}>
          <div className="card" style={{ width: '480px', maxHeight: '90vh', overflowY: 'auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <h3>Upload Raw Newsroom Media</h3>
              <button onClick={() => setUploadModalOpen(false)} style={{ background: 'none', border: 'none', fontSize: '1.2rem', cursor: 'pointer' }}>✖</button>
            </div>

            <form onSubmit={handleUploadSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.3rem' }}>Select Media File (Max 500MB):</label>
                <input
                  type="file"
                  accept="video/*,audio/*,image/*"
                  onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                  required
                  style={{ width: '100%' }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.3rem' }}>Story Association (Optional):</label>
                <select
                  value={selectedStoryId}
                  onChange={(e) => setSelectedStoryId(e.target.value)}
                  style={{ width: '100%', padding: '0.5rem', borderRadius: '4px', border: '1px solid #cbd5e1' }}
                >
                  <option value="">-- Standalone Media (No Story) --</option>
                  {stories.map((s) => (
                    <option key={s.id} value={s.id}>{s.title}</option>
                  ))}
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.3rem' }}>Rights / Copyright Type:</label>
                <select
                  value={rightsType}
                  onChange={(e) => setRightsType(e.target.value)}
                  style={{ width: '100%', padding: '0.5rem', borderRadius: '4px', border: '1px solid #cbd5e1' }}
                >
                  <option value="OWNED">OWNED (News 9 Original Content)</option>
                  <option value="LICENSED">LICENSED (Wire / Syndicated Partner)</option>
                  <option value="USER_PROVIDED">USER_PROVIDED (Eyewitness / PR Submission)</option>
                  <option value="RESTRICTED">RESTRICTED (Embargoed / Internal Only)</option>
                  <option value="UNKNOWN">UNKNOWN (Pending Rights Clearance)</option>
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.3rem' }}>Attribution (Source / Credit):</label>
                <input
                  type="text"
                  placeholder="e.g. Associated Press / John Doe"
                  value={attribution}
                  onChange={(e) => setAttribution(e.target.value)}
                  style={{ width: '100%', padding: '0.5rem', borderRadius: '4px', border: '1px solid #cbd5e1' }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.3rem' }}>License / Contract Details:</label>
                <input
                  type="text"
                  placeholder="e.g. Associated Press Wire Agreement 2026"
                  value={licenseDetails}
                  onChange={(e) => setLicenseDetails(e.target.value)}
                  style={{ width: '100%', padding: '0.5rem', borderRadius: '4px', border: '1px solid #cbd5e1' }}
                />
              </div>

              <div>
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem' }}>
                  <input
                    type="checkbox"
                    checked={reusePermitted}
                    onChange={(e) => setReusePermitted(e.target.checked)}
                  />
                  <span>Derivative creation explicitly permitted under newsroom license policy</span>
                </label>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.5rem' }}>
                <button
                  type="button"
                  onClick={() => setUploadModalOpen(false)}
                  style={{ padding: '0.5rem 1rem', backgroundColor: '#f1f5f9', border: '1px solid #cbd5e1', borderRadius: '4px', cursor: 'pointer' }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={uploading}
                  style={{
                    padding: '0.5rem 1.2rem',
                    backgroundColor: 'var(--accent-red)',
                    color: '#fff',
                    border: 'none',
                    borderRadius: '4px',
                    cursor: 'pointer',
                    fontWeight: 600,
                  }}
                >
                  {uploading ? 'Uploading...' : 'Confirm Upload'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Mandatory Rejection Reason Modal */}
      {rejectionTarget && (
        <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}>
          <div className="card" style={{ width: '420px' }}>
            <h3 style={{ marginBottom: '0.75rem' }}>Mandatory Editorial Rejection Reason</h3>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '0.75rem' }}>
              Please state why this {rejectionTarget.type === 'clip' ? 'clip candidate' : 'thumbnail'} is rejected:
            </p>
            <textarea
              rows={3}
              value={rejectionReason}
              onChange={(e) => setRejectionReason(e.target.value)}
              placeholder="e.g. Unverified quotation or poor framing..."
              style={{ width: '100%', padding: '0.5rem', borderRadius: '4px', border: '1px solid #cbd5e1', marginBottom: '1rem' }}
            />
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem' }}>
              <button
                onClick={() => setRejectionTarget(null)}
                style={{ padding: '0.4rem 0.8rem', backgroundColor: '#f1f5f9', border: '1px solid #cbd5e1', borderRadius: '4px', cursor: 'pointer' }}
              >
                Cancel
              </button>
              <button
                disabled={!rejectionReason.trim()}
                onClick={() => submitReview(rejectionTarget.type, rejectionTarget.id, 'REJECT', rejectionReason)}
                style={{
                  padding: '0.4rem 1rem',
                  backgroundColor: '#ef4444',
                  color: '#fff',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: rejectionReason.trim() ? 'pointer' : 'not-allowed',
                  fontWeight: 600,
                }}
              >
                Confirm Rejection
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
