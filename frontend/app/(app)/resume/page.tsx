"use client";
import { useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { resume as resumeApi, ResumeData } from "@/lib/api";
import { Upload, FileText, CheckCircle } from "lucide-react";

export default function ResumePage() {
  const qc = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);

  const { data: activeResume } = useQuery<ResumeData>({
    queryKey: ["resume-active"],
    queryFn: resumeApi.active,
    retry: false,
  });

  const handleFile = async (file: File) => {
    setUploading(true);
    try {
      await resumeApi.upload(file);
      await qc.invalidateQueries({ queryKey: ["resume-active"] });
      toast.success("Resume uploaded and parsed successfully");
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  };

  const sd = activeResume?.structured_data;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Resume</h1>
        <p className="text-sm text-zinc-400 mt-1">Upload your resume — Claude parses and tailors it for each job</p>
      </div>

      {/* Upload zone */}
      <div
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        className={`cursor-pointer rounded-xl border-2 border-dashed p-10 text-center transition-colors ${
          dragOver ? "border-white/30 bg-white/5" : "border-white/10 hover:border-white/20 hover:bg-white/3"
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.docx,.doc"
          className="hidden"
          onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
        />
        {uploading ? (
          <div className="flex flex-col items-center gap-3">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-white/20 border-t-white" />
            <p className="text-sm text-zinc-400">Parsing resume with AI…</p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-white/10 bg-white/5">
              <Upload className="h-5 w-5 text-zinc-400" />
            </div>
            <div>
              <p className="text-sm font-medium text-zinc-200">
                {activeResume ? "Upload a new version" : "Upload your resume"}
              </p>
              <p className="text-xs text-zinc-500 mt-1">PDF or DOCX · Max 10MB</p>
            </div>
          </div>
        )}
      </div>

      {/* Parsed preview */}
      {activeResume && sd && (
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <CheckCircle className="h-4 w-4 text-emerald-400" />
            <span className="text-sm font-medium text-zinc-200">
              {activeResume.filename}
            </span>
            <span className="text-xs text-zinc-500">
              Parsed {activeResume.parsed_at ? new Date(activeResume.parsed_at).toLocaleDateString() : ""}
            </span>
          </div>

          {/* Skills */}
          {sd.skills && sd.skills.length > 0 && (
            <div className="rounded-xl border border-white/8 bg-white/3 p-5">
              <h3 className="text-xs font-medium text-zinc-400 mb-3">Skills detected</h3>
              <div className="flex flex-wrap gap-1.5">
                {sd.skills.map((skill) => (
                  <span key={skill} className="text-xs bg-white/6 border border-white/8 text-zinc-300 px-2.5 py-1 rounded-full">
                    {skill}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Experience */}
          {sd.experience && sd.experience.length > 0 && (
            <div className="rounded-xl border border-white/8 bg-white/3 p-5 space-y-4">
              <h3 className="text-xs font-medium text-zinc-400">Experience</h3>
              {sd.experience.map((exp, i) => (
                <div key={i}>
                  <p className="text-sm font-medium text-zinc-200">{exp.role}</p>
                  <p className="text-xs text-zinc-400 mb-2">{exp.company} {exp.start ? `· ${exp.start}–${exp.end || "Present"}` : ""}</p>
                  <ul className="space-y-1">
                    {exp.bullets.slice(0, 3).map((b, j) => (
                      <li key={j} className="text-xs text-zinc-500 pl-3 relative before:content-['•'] before:absolute before:left-0 before:text-zinc-600">
                        {b}
                      </li>
                    ))}
                    {exp.bullets.length > 3 && (
                      <li className="text-xs text-zinc-600">+{exp.bullets.length - 3} more</li>
                    )}
                  </ul>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
