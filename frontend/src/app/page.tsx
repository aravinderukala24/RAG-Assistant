"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import {
  GitBranch, Send, FolderTree, ChevronRight, ChevronDown,
  FileCode, Loader2, Search, ArrowRight, Code2, MessageSquare,
  BookOpen, Zap, X, File, Copy, Check, Download, Database,
  Braces, Cpu, CheckCircle2, Circle, AlertCircle
} from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

// ─── Types ────────────────────────────────────────────────
interface CodeSource {
  file_path: string;
  function_name?: string | null;
  class_name?: string | null;
  start_line: number;
  end_line: number;
  language: string;
  snippet: string;
  similarity_score?: number | null;
}

interface TraceStep {
  step_number: number;
  title: string;
  description: string;
  file_path?: string | null;
  function_name?: string | null;
  line_range?: string | null;
}

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  sources?: CodeSource[];
  trace_flow?: TraceStep[];
}

interface FileNode {
  name: string;
  path: string;
  type: "file" | "directory";
  language?: string | null;
  children?: FileNode[] | null;
}

interface RepoInfo {
  repository: string;
  repo_name: string;
  files_scanned: number;
  chunks_indexed: number;
  languages: string[];
}

interface ProgressEvent {
  stage: string;
  status: string;
  detail?: string;
  progress: number;
  current?: number;
  total?: number;
  result?: RepoInfo;
}

// ─── Stage Config ─────────────────────────────────────────
const STAGES = [
  { key: "cloning",   label: "Clone Repository",    icon: Download },
  { key: "scanning",  label: "Scan Source Files",    icon: Search },
  { key: "chunking",  label: "Parse & Chunk Code",  icon: Braces },
  { key: "embedding", label: "Generate Embeddings",  icon: Cpu },
  { key: "indexing",  label: "Build Search Index",   icon: Database },
];

// ─── Helper Components ────────────────────────────────────

function TreeNode({ node, depth = 0 }: { node: FileNode; depth?: number }) {
  const [open, setOpen] = useState(depth < 1);
  const isDir = node.type === "directory";
  return (
    <div>
      <button
        onClick={() => isDir && setOpen(!open)}
        className="flex items-center w-full text-left py-1 px-2 hover:bg-white/5 rounded text-sm group"
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
      >
        {isDir ? (
          open ? <ChevronDown size={14} className="mr-1 text-indigo-400" /> : <ChevronRight size={14} className="mr-1 text-indigo-400" />
        ) : (
          <FileCode size={14} className="mr-1 text-slate-500" />
        )}
        <span className={`truncate ${isDir ? "text-indigo-300 font-medium" : "text-slate-300"}`}>
          {node.name}
        </span>
        {node.language && (
          <span className="ml-auto text-[10px] text-slate-600 opacity-0 group-hover:opacity-100">
            {node.language}
          </span>
        )}
      </button>
      {isDir && open && node.children?.map((child, i) => (
        <TreeNode key={child.path + i} node={child} depth={depth + 1} />
      ))}
    </div>
  );
}

function SourceCard({ source, index }: { source: CodeSource; index: number }) {
  const [copied, setCopied] = useState(false);
  const copySnippet = () => {
    navigator.clipboard.writeText(source.snippet);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="border border-[#2a2a4a] rounded-lg bg-[#12121a] overflow-hidden slide-in" style={{ animationDelay: `${index * 80}ms` }}>
      <div className="flex items-center justify-between px-3 py-2 bg-[#1a1a2e] border-b border-[#2a2a4a]">
        <div className="flex items-center gap-2 min-w-0">
          <File size={13} className="text-indigo-400 flex-shrink-0" />
          <span className="text-xs font-mono text-indigo-300 truncate">{source.file_path}</span>
        </div>
        <button onClick={copySnippet} className="text-slate-500 hover:text-white p-1">
          {copied ? <Check size={12} className="text-green-400" /> : <Copy size={12} />}
        </button>
      </div>
      <div className="px-3 py-2 space-y-1">
        {source.function_name && (
          <div className="flex items-center gap-1.5 text-xs">
            <Code2 size={11} className="text-purple-400" />
            <span className="text-purple-300 font-mono">{source.class_name ? `${source.class_name}.` : ""}{source.function_name}()</span>
          </div>
        )}
        <div className="text-[11px] text-slate-500">
          Lines {source.start_line}–{source.end_line} &middot; {source.language}
          {source.similarity_score != null && ` · ${(source.similarity_score * 100).toFixed(0)}% match`}
        </div>
      </div>
      <pre className="px-3 py-2 text-[11px] leading-relaxed text-slate-300 bg-[#0d0d14] overflow-x-auto max-h-48 border-t border-[#2a2a4a]">
        <code>{source.snippet}</code>
      </pre>
    </div>
  );
}

function TraceFlow({ steps }: { steps: TraceStep[] }) {
  if (!steps.length) return null;
  return (
    <div className="mt-4 p-4 rounded-lg border border-indigo-500/30 bg-indigo-950/20">
      <h4 className="text-sm font-semibold text-indigo-300 mb-3 flex items-center gap-2">
        <Zap size={14} /> Execution Trace
      </h4>
      <div className="space-y-1">
        {steps.map((step, i) => (
          <div key={i} className="flex items-start gap-3 slide-in" style={{ animationDelay: `${i * 100}ms` }}>
            <div className="flex flex-col items-center flex-shrink-0">
              <div className="w-7 h-7 rounded-full bg-indigo-500/20 border border-indigo-500/40 flex items-center justify-center text-xs font-bold text-indigo-300">
                {step.step_number}
              </div>
              {i < steps.length - 1 && <div className="w-px h-6 bg-indigo-500/20 mt-1" />}
            </div>
            <div className="pb-3 min-w-0">
              <div className="text-sm font-medium text-slate-200">{step.title}</div>
              <div className="text-xs text-slate-400 mt-0.5">{step.description}</div>
              {step.file_path && (
                <div className="text-[10px] text-indigo-400 font-mono mt-1">
                  {step.file_path}{step.function_name ? ` → ${step.function_name}()` : ""}{step.line_range ? ` L${step.line_range}` : ""}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Progress Overlay ─────────────────────────────────────
function ProgressOverlay({ event }: { event: ProgressEvent }) {
  const currentStageIndex = STAGES.findIndex(s => s.key === event.stage);
  const isComplete = event.stage === "complete";
  const isError = event.stage === "error";

  return (
    <div className="flex-1 flex items-center justify-center p-6">
      <div className="w-full max-w-xl space-y-8">
        {/* Header */}
        <div className="text-center space-y-2">
          {isComplete ? (
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-green-500/10 border border-green-500/30">
              <CheckCircle2 size={20} className="text-green-400" />
              <span className="text-sm font-semibold text-green-300">Repository Ready</span>
            </div>
          ) : isError ? (
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-red-500/10 border border-red-500/30">
              <AlertCircle size={20} className="text-red-400" />
              <span className="text-sm font-semibold text-red-300">Analysis Failed</span>
            </div>
          ) : (
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-indigo-500/10 border border-indigo-500/30">
              <Loader2 size={20} className="text-indigo-400 animate-spin" />
              <span className="text-sm font-semibold text-indigo-300">Analyzing Repository</span>
            </div>
          )}
        </div>

        {/* Progress Bar */}
        <div className="space-y-2">
          <div className="flex justify-between items-center text-sm">
            <span className="text-slate-400">{event.status}</span>
            <span className="font-mono font-bold text-lg text-indigo-300">{event.progress}%</span>
          </div>
          <div className="h-3 rounded-full bg-[#1a1a2e] border border-[#2a2a4a] overflow-hidden relative">
            <div
              className="h-full rounded-full transition-all duration-700 ease-out relative overflow-hidden"
              style={{
                width: `${event.progress}%`,
                background: isComplete
                  ? "linear-gradient(90deg, #22c55e, #16a34a)"
                  : isError
                  ? "linear-gradient(90deg, #ef4444, #dc2626)"
                  : "linear-gradient(90deg, #6366f1, #8b5cf6, #a78bfa)",
              }}
            >
              {/* Animated shine effect */}
              {!isComplete && !isError && (
                <div className="absolute inset-0 animate-shimmer" style={{
                  background: "linear-gradient(90deg, transparent, rgba(255,255,255,0.15), transparent)",
                  backgroundSize: "200% 100%",
                }} />
              )}
            </div>
          </div>
          {event.detail && (
            <div className="text-xs text-slate-500 text-center">{event.detail}</div>
          )}
        </div>

        {/* Stage List */}
        <div className="space-y-1.5">
          {STAGES.map((stage, idx) => {
            const isDone = isComplete || (currentStageIndex >= 0 && idx < currentStageIndex);
            const isCurrent = !isComplete && !isError && stage.key === event.stage;
            const isPending = !isDone && !isCurrent;
            const Icon = stage.icon;

            return (
              <div
                key={stage.key}
                className={`flex items-center gap-3 px-4 py-2.5 rounded-lg border transition-all duration-500 ${
                  isDone
                    ? "bg-green-500/5 border-green-500/20"
                    : isCurrent
                    ? "bg-indigo-500/10 border-indigo-500/30 shadow-md shadow-indigo-500/5"
                    : "bg-[#12121a]/50 border-transparent opacity-40"
                }`}
              >
                {/* Status icon */}
                <div className="flex-shrink-0">
                  {isDone ? (
                    <CheckCircle2 size={18} className="text-green-400" />
                  ) : isCurrent ? (
                    <Loader2 size={18} className="text-indigo-400 animate-spin" />
                  ) : (
                    <Circle size={18} className="text-slate-600" />
                  )}
                </div>

                {/* Stage icon + label */}
                <Icon size={16} className={isDone ? "text-green-400/70" : isCurrent ? "text-indigo-400" : "text-slate-600"} />
                <span className={`text-sm font-medium ${isDone ? "text-green-300/80" : isCurrent ? "text-indigo-200" : "text-slate-600"}`}>
                  {stage.label}
                </span>

                {/* Current/Total counter for embedding/chunking */}
                {isCurrent && event.current != null && event.total != null && (
                  <span className="ml-auto text-xs font-mono text-indigo-400">
                    {event.current} / {event.total}
                  </span>
                )}

                {/* Done checkmark text */}
                {isDone && (
                  <span className="ml-auto text-[10px] text-green-500/60 uppercase tracking-wider font-semibold">Done</span>
                )}
              </div>
            );
          })}
        </div>

        {/* Error message */}
        {isError && (
          <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-300 text-sm">
            {event.status}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────

interface RepoHistoryItem {
  repoInfo: RepoInfo;
  messages: ChatMessage[];
  timestamp: number;
}

export default function Home() {
  const [repoUrl, setRepoUrl] = useState("");
  const [repoInfo, setRepoInfo] = useState<RepoInfo | null>(null);
  const [fileTree, setFileTree] = useState<FileNode[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState("");
  const [activeSources, setActiveSources] = useState<CodeSource[]>([]);
  const [activeTrace, setActiveTrace] = useState<TraceStep[]>([]);
  const [progressEvent, setProgressEvent] = useState<ProgressEvent | null>(null);
  
  // History state
  const [history, setHistory] = useState<Record<string, RepoHistoryItem>>({});
  const [historySidebarOpen, setHistorySidebarOpen] = useState(true);

  const chatEndRef = useRef<HTMLDivElement>(null);

  // Load history on mount
  useEffect(() => {
    try {
      const saved = localStorage.getItem("rag_assistant_history");
      if (saved) setHistory(JSON.parse(saved));
    } catch (e) {
      console.error("Failed to load history", e);
    }
  }, []);

  // Save history on change
  useEffect(() => {
    if (Object.keys(history).length > 0) {
      localStorage.setItem("rag_assistant_history", JSON.stringify(history));
    } else {
      localStorage.removeItem("rag_assistant_history");
    }
  }, [history]);

  // Update current repo history when messages change
  useEffect(() => {
    if (repoInfo && !analyzing) {
      setHistory(prev => ({
        ...prev,
        [repoInfo.repository]: {
          repoInfo,
          messages,
          timestamp: Date.now(),
        }
      }));
    }
  }, [messages, repoInfo, analyzing]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const loadTree = async (repository: string) => {
    try {
      const treeRes = await fetch(`${API_BASE}/api/repositories/tree?repository=${encodeURIComponent(repository)}`);
      if (treeRes.ok) {
        const treeData = await treeRes.json();
        setFileTree(treeData.tree || []);
      }
    } catch { /* ignore tree errors */ }
  };

  const analyzeRepo = useCallback(async () => {
    if (!repoUrl.trim()) return;
    setAnalyzing(true);
    setError("");
    setProgressEvent({ stage: "starting", status: "Connecting...", progress: 0 });

    try {
      const res = await fetch(`${API_BASE}/api/repositories/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repo_url: repoUrl.trim() }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Server error ${res.status}`);
      }

      // Read SSE stream
      const reader = res.body?.getReader();
      if (!reader) throw new Error("No response body");

      const decoder = new TextDecoder();
      let buffer = "";
      let finalResult: RepoInfo | null = null;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // Parse SSE events from buffer
        const lines = buffer.split("\n");
        buffer = lines.pop() || ""; // keep incomplete line in buffer

        for (const line of lines) {
          const trimmed = line.trim();
          if (trimmed.startsWith("data: ")) {
            try {
              const event: ProgressEvent = JSON.parse(trimmed.slice(6));
              setProgressEvent(event);

              if (event.stage === "complete" && event.result) {
                finalResult = event.result;
              }
              if (event.stage === "error") {
                throw new Error(event.status);
              }
            } catch (parseErr) {
              if (parseErr instanceof Error && parseErr.message !== trimmed.slice(6)) {
                if ((parseErr as Error).message.startsWith("Failed") || (parseErr as Error).message.startsWith("No supported")) {
                  throw parseErr;
                }
              }
            }
          }
        }
      }

      if (finalResult) {
        setRepoInfo(finalResult);
        // Do not clear messages if this repo already exists in history
        const existing = history[finalResult.repository];
        if (existing) {
          setMessages(existing.messages || []);
        } else {
          setMessages([]);
        }
        setActiveSources([]);
        setActiveTrace([]);
        await loadTree(finalResult.repository);
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Failed to analyze repository";
      setError(msg);
      setProgressEvent({ stage: "error", status: msg, progress: 0 });
    } finally {
      setAnalyzing(false);
    }
  }, [repoUrl, history]);

  const loadHistoryItem = (repoKey: string) => {
    const item = history[repoKey];
    if (item) {
      setRepoInfo(item.repoInfo);
      setMessages(item.messages || []);
      setActiveSources([]);
      setActiveTrace([]);
      loadTree(repoKey);
    }
  };

  const deleteHistoryItem = (repoKey: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const newHistory = { ...history };
    delete newHistory[repoKey];
    setHistory(newHistory);
    if (repoInfo?.repository === repoKey) {
      handleNewRepo();
    }
  };

  const handleNewRepo = () => {
    setRepoInfo(null);
    setRepoUrl("");
    setMessages([]);
    setFileTree([]);
    setActiveSources([]);
    setActiveTrace([]);
    setProgressEvent(null);
  };

  const askQuestion = useCallback(async () => {
    if (!question.trim() || !repoInfo) return;
    const q = question.trim();
    setQuestion("");
    setMessages(prev => [...prev, { role: "user", content: q }]);
    setLoading(true);

    try {
      const res = await fetch(`${API_BASE}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repository: repoInfo.repository, question: q }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Server error ${res.status}`);
      }
      const data = await res.json();
      setMessages(prev => [...prev, {
        role: "assistant",
        content: data.answer,
        sources: data.sources,
        trace_flow: data.trace_flow,
      }]);
      setActiveSources(data.sources || []);
      setActiveTrace(data.trace_flow || []);
    } catch (e: unknown) {
      setMessages(prev => [...prev, {
        role: "assistant",
        content: `Error: ${e instanceof Error ? e.message : "Failed to get answer"}`,
      }]);
    } finally {
      setLoading(false);
    }
  }, [question, repoInfo]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (repoInfo) askQuestion();
      else analyzeRepo();
    }
  };

  const sampleQuestions = [
    "What is the overall architecture?",
    "Where is authentication handled?",
    "How is the database connection set up?",
    "Where is the main entry point?",
    "Trace the login flow",
  ];

  const sortedHistory = Object.values(history).sort((a, b) => b.timestamp - a.timestamp);

  // ── History Sidebar Component ──
  const HistorySidebar = () => {
    if (!historySidebarOpen) {
      return (
        <div className="w-12 border-r border-[#2a2a4a] bg-[#0d0d14] flex flex-col items-center py-4 flex-shrink-0">
          <button onClick={() => setHistorySidebarOpen(true)} className="p-2 rounded hover:bg-white/5 text-slate-400 hover:text-white" title="Open History">
            <ChevronRight size={18} />
          </button>
          <button onClick={handleNewRepo} className="mt-4 p-2 rounded hover:bg-white/5 text-indigo-400 hover:text-indigo-300" title="New Repository">
            <Code2 size={18} />
          </button>
        </div>
      );
    }

    return (
      <aside className="w-64 border-r border-[#2a2a4a] bg-[#0d0d14] flex flex-col flex-shrink-0 transition-all">
        <div className="p-3 border-b border-[#2a2a4a] flex items-center justify-between">
          <button 
            onClick={handleNewRepo}
            className="flex-1 flex items-center gap-2 px-3 py-2 rounded-lg bg-indigo-600/10 hover:bg-indigo-600/20 text-indigo-400 border border-indigo-500/20 transition-colors"
          >
            <GitBranch size={16} />
            <span className="text-sm font-medium">+ New Repository</span>
          </button>
          <button onClick={() => setHistorySidebarOpen(false)} className="ml-2 p-2 rounded hover:bg-white/5 text-slate-500 hover:text-white">
            <ChevronRight size={16} className="rotate-180" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          <div className="px-2 py-2 text-xs font-semibold text-slate-500 uppercase tracking-wide">Recent</div>
          {sortedHistory.length === 0 ? (
            <div className="px-3 py-4 text-xs text-slate-600 text-center">No history yet</div>
          ) : (
            sortedHistory.map((item) => {
              const isActive = repoInfo?.repository === item.repoInfo.repository;
              return (
                <div 
                  key={item.repoInfo.repository}
                  onClick={() => loadHistoryItem(item.repoInfo.repository)}
                  className={`group flex items-center justify-between px-3 py-2.5 rounded-lg cursor-pointer transition-colors ${
                    isActive ? "bg-indigo-500/10 border border-indigo-500/20" : "hover:bg-white/5 border border-transparent"
                  }`}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <MessageSquare size={14} className={isActive ? "text-indigo-400" : "text-slate-500"} />
                    <span className={`text-sm truncate ${isActive ? "text-indigo-300" : "text-slate-300"}`}>
                      {item.repoInfo.repo_name.split("/").pop()}
                    </span>
                  </div>
                  <button 
                    onClick={(e) => deleteHistoryItem(item.repoInfo.repository, e)}
                    className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-white/10 text-slate-500 hover:text-red-400 transition-opacity"
                    title="Remove from history"
                  >
                    <X size={12} />
                  </button>
                </div>
              );
            })
          )}
        </div>
      </aside>
    );
  };

  // ── Progress View (during analysis) ──
  if (analyzing && progressEvent) {
    return (
      <div className="flex-1 flex flex-col h-screen overflow-hidden">
        <ProgressOverlay event={progressEvent} />
      </div>
    );
  }

  // ── Landing View ──
  if (!repoInfo) {
    return (
      <div className="flex-1 flex h-screen overflow-hidden">
        <HistorySidebar />
        <div className="flex-1 flex items-center justify-center p-6 overflow-y-auto">
          <div className="w-full max-w-2xl space-y-8">
            {/* Title */}
            <div className="text-center space-y-3">
              <div className="inline-flex items-center gap-3 px-4 py-2 rounded-full bg-indigo-500/10 border border-indigo-500/20">
                <Code2 size={20} className="text-indigo-400" />
                <span className="text-sm font-medium text-indigo-300">AI-Powered Code Intelligence</span>
              </div>
              <h1 className="text-4xl font-bold bg-gradient-to-r from-indigo-400 via-purple-400 to-indigo-300 bg-clip-text text-transparent">
                Codebase RAG Assistant
              </h1>
              <p className="text-slate-400 max-w-lg mx-auto">
                Understand any public GitHub repository in seconds. Ask natural language questions
                and get grounded answers with file, function, and line references.
              </p>
            </div>

            {/* Input */}
            <div className="relative">
              <div className="flex items-center gap-3 px-4 py-3 rounded-xl border bg-[#12121a] border-[#2a2a4a] hover:border-[#3a3a5a] focus-within:border-indigo-500">
                <GitBranch size={20} className="text-slate-500 flex-shrink-0" />
                <input
                  type="text"
                  value={repoUrl}
                  onChange={(e) => setRepoUrl(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="https://github.com/owner/repo"
                  className="flex-1 bg-transparent outline-none text-slate-200 placeholder:text-slate-600"
                />
                <button
                  onClick={analyzeRepo}
                  disabled={!repoUrl.trim()}
                  className="px-5 py-2 rounded-lg bg-gradient-to-r from-indigo-600 to-purple-600 text-white font-medium text-sm hover:from-indigo-500 hover:to-purple-500 disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-2"
                >
                  <Search size={16} />
                  Analyze
                </button>
              </div>
            </div>

            {error && (
              <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-300 text-sm">
                {error}
              </div>
            )}

            {/* Quick Start */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {[
                { url: "https://github.com/pallets/flask", label: "Flask", desc: "Python web framework" },
                { url: "https://github.com/expressjs/express", label: "Express", desc: "Node.js framework" },
                { url: "https://github.com/gin-gonic/gin", label: "Gin", desc: "Go web framework" },
              ].map((ex) => (
                <button
                  key={ex.url}
                  onClick={() => setRepoUrl(ex.url)}
                  className="p-3 rounded-lg border border-[#2a2a4a] bg-[#12121a] hover:border-indigo-500/50 hover:bg-indigo-500/5 text-left"
                >
                  <div className="text-sm font-medium text-slate-200">{ex.label}</div>
                  <div className="text-xs text-slate-500 mt-0.5">{ex.desc}</div>
                </button>
              ))}
            </div>

            {/* Features */}
            <div className="grid grid-cols-3 gap-4 pt-4">
              {[
                { icon: <FolderTree size={18} />, t: "Multi-Language", d: "Python, JS, TS, Java, Go, C/C++" },
                { icon: <MessageSquare size={18} />, t: "Grounded Answers", d: "Every answer cites exact source files" },
                { icon: <Zap size={18} />, t: "Trace Flows", d: "Visualize execution paths through code" },
              ].map((f, i) => (
                <div key={i} className="text-center p-4 rounded-lg bg-[#12121a]/50">
                  <div className="inline-flex items-center justify-center w-10 h-10 rounded-lg bg-indigo-500/10 text-indigo-400 mb-2">{f.icon}</div>
                  <div className="text-sm font-medium text-slate-300">{f.t}</div>
                  <div className="text-xs text-slate-500 mt-1">{f.d}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ── Dashboard View ──
  return (
    <div className="flex-1 flex flex-col h-screen overflow-hidden">
      {/* Header */}
      <header className="flex items-center justify-between px-4 py-2.5 border-b border-[#2a2a4a] bg-[#0d0d14]">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-indigo-500/10 border border-indigo-500/20">
            <Code2 size={16} className="text-indigo-400" />
            <span className="text-sm font-semibold text-indigo-300">RAG Assistant</span>
          </div>
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#1a1a2e] border border-[#2a2a4a]">
            <GitBranch size={14} className="text-slate-400" />
            <span className="text-sm font-mono text-slate-300">{repoInfo.repo_name}</span>
          </div>
        </div>
        <div className="flex items-center gap-4 text-xs text-slate-500">
          <span><strong className="text-slate-300">{repoInfo.files_scanned}</strong> files</span>
          <span><strong className="text-slate-300">{repoInfo.chunks_indexed}</strong> chunks</span>
          <span>{repoInfo.languages.map(l => (
            <span key={l} className="inline-block px-1.5 py-0.5 rounded bg-[#1a1a2e] text-slate-400 text-[10px] font-mono mr-1">{l}</span>
          ))}</span>
        </div>
      </header>

      {/* Four-panel layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* FAR LEFT - History Sidebar */}
        <HistorySidebar />

        {/* LEFT – File Explorer */}
        <aside className="w-64 border-r border-[#2a2a4a] bg-[#0d0d14] flex flex-col flex-shrink-0">
          <div className="px-3 py-2.5 border-b border-[#2a2a4a] flex items-center gap-2">
            <FolderTree size={14} className="text-indigo-400" />
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wide">Explorer</span>
          </div>
          <div className="flex-1 overflow-y-auto py-1">
            {fileTree.map((node, i) => <TreeNode key={node.path + i} node={node} />)}
            {!fileTree.length && (
              <div className="p-4 text-xs text-slate-600 text-center">No files to display</div>
            )}
          </div>
        </aside>

        {/* CENTER – Chat */}
        <main className="flex-1 flex flex-col min-w-0">
          <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
            {messages.length === 0 && (
              <div className="flex flex-col items-center justify-center h-full text-center space-y-4 opacity-80">
                <BookOpen size={40} className="text-indigo-500/40" />
                <p className="text-slate-400 text-sm">Ask anything about <strong className="text-indigo-300">{repoInfo.repo_name}</strong></p>
                <div className="flex flex-wrap gap-2 justify-center max-w-md">
                  {sampleQuestions.map((sq) => (
                    <button
                      key={sq}
                      onClick={() => { setQuestion(sq); }}
                      className="px-3 py-1.5 rounded-full text-xs border border-[#2a2a4a] text-slate-400 hover:text-indigo-300 hover:border-indigo-500/40 hover:bg-indigo-500/5"
                    >
                      {sq}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((msg, i) => (
              <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[80%] rounded-xl px-4 py-3 slide-in ${
                  msg.role === "user"
                    ? "bg-indigo-600/20 border border-indigo-500/30 text-slate-200"
                    : "bg-[#16162a] border border-[#2a2a4a] text-slate-300"
                }`}>
                  <div className="text-sm whitespace-pre-wrap leading-relaxed">{msg.content}</div>
                  {msg.trace_flow && msg.trace_flow.length > 0 && <TraceFlow steps={msg.trace_flow} />}
                  {msg.sources && msg.sources.length > 0 && (
                    <button
                      onClick={() => { setActiveSources(msg.sources!); setActiveTrace(msg.trace_flow || []); }}
                      className="mt-3 text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1"
                    >
                      <BookOpen size={12} /> View {msg.sources.length} source references <ArrowRight size={10} />
                    </button>
                  )}
                </div>
              </div>
            ))}

            {loading && (
              <div className="flex justify-start">
                <div className="bg-[#16162a] border border-[#2a2a4a] rounded-xl px-4 py-3 flex items-center gap-3">
                  <Loader2 size={16} className="animate-spin text-indigo-400" />
                  <span className="text-sm text-slate-400">Searching codebase and reasoning...</span>
                </div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>

          {/* Input bar */}
          <div className="px-6 py-3 border-t border-[#2a2a4a] bg-[#0d0d14]">
            <div className="flex items-center gap-3 px-4 py-2.5 rounded-xl border border-[#2a2a4a] bg-[#12121a] focus-within:border-indigo-500">
              <input
                type="text"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask about the codebase..."
                disabled={loading}
                className="flex-1 bg-transparent outline-none text-sm text-slate-200 placeholder:text-slate-600"
              />
              <button
                onClick={askQuestion}
                disabled={loading || !question.trim()}
                className="p-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white disabled:opacity-30 disabled:cursor-not-allowed"
              >
                <Send size={16} />
              </button>
            </div>
          </div>
        </main>

        {/* RIGHT – Sources Panel */}
        <aside className="w-80 border-l border-[#2a2a4a] bg-[#0d0d14] flex flex-col flex-shrink-0">
          <div className="px-3 py-2.5 border-b border-[#2a2a4a] flex items-center gap-2">
            <BookOpen size={14} className="text-indigo-400" />
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wide">Sources & Evidence</span>
          </div>
          <div className="flex-1 overflow-y-auto p-3 space-y-3">
            {activeTrace.length > 0 && <TraceFlow steps={activeTrace} />}
            {activeSources.length > 0 ? (
              activeSources.map((src, i) => <SourceCard key={i} source={src} index={i} />)
            ) : (
              <div className="flex flex-col items-center justify-center h-full text-center opacity-50 space-y-2">
                <Search size={30} className="text-slate-600" />
                <p className="text-xs text-slate-600">Source references will appear here after you ask a question</p>
              </div>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
