import React, { useState, useEffect } from 'react';
import { X, Download, Database, Trash2, Video, CheckCircle2, FileText, Sparkles, RefreshCw, Layers } from 'lucide-react';
import { dataRecorder } from '../services/dataRecorder';
import { RecordedSample } from '../types/dataset';
import { sounds } from '../services/audio';

interface DataCollectorModalProps {
  isOpen: boolean;
  onClose: () => void;
  onDatasetUpdated: () => void;
}

export const DataCollectorModal: React.FC<DataCollectorModalProps> = ({
  isOpen,
  onClose,
  onDatasetUpdated,
}) => {
  const [samples, setSamples] = useState<RecordedSample[]>([]);
  const [selectedSample, setSelectedSample] = useState<RecordedSample | null>(null);
  const [isExporting, setIsExporting] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const loadSamples = async () => {
    setIsLoading(true);
    const data = await dataRecorder.getAllSamples();
    setSamples(data);
    if (data.length > 0 && !selectedSample) {
      setSelectedSample(data[0]);
    }
    setIsLoading(false);
  };

  useEffect(() => {
    if (isOpen) {
      loadSamples();
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleDelete = async (id: string) => {
    sounds.playTap();
    await dataRecorder.deleteSample(id);
    await loadSamples();
    onDatasetUpdated();
    if (selectedSample?.id === id) {
      setSelectedSample(null);
    }
  };

  const handleExportZip = async () => {
    sounds.playTap();
    setIsExporting(true);
    try {
      const zipBlob = await dataRecorder.exportDatasetZip();
      const url = URL.createObjectURL(zipBlob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `SignIt_ISL_Dataset_${new Date().toISOString().slice(0, 10)}.zip`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      sounds.playFanfare();
    } catch (err) {
      console.error('Export error:', err);
    } finally {
      setIsExporting(false);
    }
  };

  const totalFrames = samples.reduce((acc, s) => acc + s.totalFrames, 0);
  const totalSeconds = Math.round(samples.reduce((acc, s) => acc + s.durationMs, 0) / 1000);

  return (
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-3 sm:p-5">
      <div className="bg-white rounded-3xl max-w-4xl w-full border-4 border-sky-400 shadow-2xl flex flex-col max-h-[90vh] overflow-hidden animate-in zoom-in-95 duration-200">
        {/* Header */}
        <div className="bg-slate-50 px-6 py-4 border-b border-slate-200 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-red-100 text-red-600 flex items-center justify-center text-xl shadow-inner">
              <Database className="w-5 h-5 text-red-500" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="font-extrabold text-lg text-slate-800">
                  ISL Research Dataset Hub
                </h2>
                <span className="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 text-[10px] font-black uppercase">
                  Google MediaPipe Format
                </span>
              </div>
              <p className="text-xs text-slate-500">
                Synchronized 3D Hand/Face landmarks & video clips for retraining ISL models.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              disabled={samples.length === 0 || isExporting}
              onClick={handleExportZip}
              className="btn-duo-primary px-4 py-2 rounded-xl text-xs font-black flex items-center gap-2 shadow-sm disabled:opacity-50"
            >
              {isExporting ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  Zipping Dataset...
                </>
              ) : (
                <>
                  <Download className="w-3.5 h-3.5" />
                  Export Dataset (.ZIP)
                </>
              )}
            </button>
            <button
              onClick={onClose}
              className="p-2 rounded-xl text-slate-400 hover:text-slate-700 hover:bg-slate-200/50"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Stats Row */}
        <div className="bg-sky-50/70 border-b border-sky-100 px-6 py-3 grid grid-cols-4 gap-3 text-center">
          <div>
            <div className="text-[10px] font-bold text-sky-600 uppercase">Recorded Clips</div>
            <div className="text-lg font-black text-sky-900">{samples.length}</div>
          </div>
          <div>
            <div className="text-[10px] font-bold text-sky-600 uppercase">Total Frames</div>
            <div className="text-lg font-black text-sky-900">{totalFrames}</div>
          </div>
          <div>
            <div className="text-[10px] font-bold text-sky-600 uppercase">Duration</div>
            <div className="text-lg font-black text-sky-900">{totalSeconds}s</div>
          </div>
          <div>
            <div className="text-[10px] font-bold text-sky-600 uppercase">Contributor ID</div>
            <div className="text-xs font-mono font-bold text-sky-800 truncate">
              {dataRecorder.getContributorId()}
            </div>
          </div>
        </div>

        {/* Body Content */}
        <div className="flex-1 overflow-hidden grid grid-cols-1 md:grid-cols-12 p-5 gap-5">
          {/* Samples List (5 cols) */}
          <div className="md:col-span-5 flex flex-col gap-3 overflow-y-auto pr-1">
            <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">
              Collected Samples ({samples.length})
            </span>

            {isLoading && (
              <div className="flex items-center justify-center p-8">
                <RefreshCw className="w-6 h-6 text-sky-500 animate-spin" />
              </div>
            )}

            {!isLoading && samples.length === 0 && (
              <div className="bg-slate-50 border border-slate-200 rounded-2xl p-6 text-center text-xs text-slate-500 flex flex-col items-center gap-2">
                <Database className="w-8 h-8 text-slate-300" />
                <span>No recordings captured yet.</span>
                <span className="text-[11px] text-slate-400">
                  Practice any sign or play PopSign Arcade with your camera to capture training data!
                </span>
              </div>
            )}

            {samples.map((s) => (
              <div
                key={s.id}
                onClick={() => setSelectedSample(s)}
                className={`p-3 rounded-2xl border-2 transition-all cursor-pointer flex items-center justify-between ${
                  selectedSample?.id === s.id
                    ? 'bg-sky-50 border-sky-400 shadow-sm'
                    : 'bg-white border-slate-200 hover:border-slate-300'
                }`}
              >
                <div>
                  <div className="font-extrabold text-sm text-slate-800 flex items-center gap-1.5">
                    <span>{s.signName}</span>
                    <span className="text-xs text-slate-400 font-normal">({s.hindiName})</span>
                  </div>
                  <div className="text-[11px] text-slate-500 flex items-center gap-2 mt-0.5 flex-wrap">
                    <span>{s.totalFrames} frames</span>
                    <span>•</span>
                    <span>{Math.round(s.durationMs / 100) / 10}s</span>
                    <span>•</span>
                    <span className={`font-bold ${s.isCorrect ? 'text-emerald-600' : 'text-amber-600'}`}>
                      {s.isCorrect ? '✓ Verified' : (s.predictedLabel ? `Guessed: ${s.predictedLabel}` : `${Math.round(s.confidenceScore * 100)}%`)}
                    </span>
                  </div>
                </div>

                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDelete(s.id);
                  }}
                  className="p-1.5 rounded-lg text-slate-400 hover:text-red-500 hover:bg-red-50 transition-colors"
                  title="Delete sample"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>

          {/* Sample Inspector & Video Player (7 cols) */}
          <div className="md:col-span-7 bg-slate-50 rounded-2xl border-2 border-slate-200 p-4 flex flex-col gap-3 overflow-y-auto">
            {selectedSample ? (
              <>
                <div className="flex items-center justify-between border-b border-slate-200 pb-2">
                  <div>
                    <h3 className="font-black text-base text-slate-800">
                      Sample Inspection: {selectedSample.signName}
                    </h3>
                    <p className="text-[11px] text-slate-500 font-mono">{selectedSample.id}</p>
                  </div>
                  <span className="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 text-xs font-bold">
                    ✓ Verified Quality
                  </span>
                </div>

                {/* Video Playback */}
                {selectedSample.videoBlobUrl ? (
                  <div className="rounded-2xl overflow-hidden bg-black aspect-video max-h-56 flex items-center justify-center border border-slate-300">
                    <video
                      src={selectedSample.videoBlobUrl}
                      controls
                      autoPlay
                      loop
                      className="w-full h-full object-contain"
                    />
                  </div>
                ) : (
                  <div className="rounded-2xl bg-slate-200 aspect-video max-h-48 flex items-center justify-center text-xs text-slate-500">
                    <Video className="w-5 h-5 mr-2 text-slate-400" />
                    Landmarks-only capture (Camera video stream saved in JSON sequences)
                  </div>
                )}

                {/* 3D Landmark JSON Raw Preview */}
                <div>
                  <div className="flex items-center justify-between text-xs font-bold text-slate-700 mb-1">
                    <span className="flex items-center gap-1">
                      <FileText className="w-3.5 h-3.5 text-sky-500" />
                      Google HandLandmarker 3D Points ({selectedSample.landmarkSequence.length} frames)
                    </span>
                    <span className="text-[10px] text-slate-400 font-mono">Format: MediaPipe v1</span>
                  </div>

                  <pre className="bg-slate-900 text-sky-300 p-3 rounded-xl text-[10px] font-mono overflow-x-auto max-h-40 border border-slate-800">
                    {JSON.stringify(
                      {
                        sample_id: selectedSample.id,
                        label: selectedSample.signId,
                        sign_name: selectedSample.signName,
                        fps: selectedSample.fps,
                        sample_frame_0: selectedSample.landmarkSequence[0] || 'empty',
                      },
                      null,
                      2
                    )}
                  </pre>
                </div>
              </>
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center text-center p-8 text-slate-400">
                <Layers className="w-10 h-10 text-slate-300 mb-2" />
                <p className="text-xs font-semibold">Select a sample on the left to inspect raw landmarks and video</p>
              </div>
            )}
          </div>
        </div>

        {/* Footer info */}
        <div className="bg-white border-t border-slate-200 px-6 py-3 flex items-center justify-between text-xs text-slate-500">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-500" />
            <span>Ethical crowdsourcing: Data stored locally until you choose to export it.</span>
          </div>
          <button
            onClick={onClose}
            className="btn-duo-secondary px-4 py-1.5 rounded-xl font-bold text-xs"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

