import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import {
  FolderPlus,
  Trash2,
  Video,
  FileText,
  ChevronRight,
  Upload,
  X,
  Loader2,
} from 'lucide-react'
import { projectsApi, videosApi } from '../api/client'
import toast from 'react-hot-toast'
import type { ProjectListItem } from '../types'
import clsx from 'clsx'

function formatDate(dateStr: string) {
  return new Date(dateStr).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function ProjectCard({ project, onDelete }: { project: ProjectListItem; onDelete: () => void }) {
  const navigate = useNavigate()
  const [showDelete, setShowDelete] = useState(false)

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      className="console-card p-4 hover:border-accent-red/30 transition-all cursor-pointer group"
      onClick={() => navigate(`/project/${project.name}`)}
      onMouseEnter={() => setShowDelete(true)}
      onMouseLeave={() => setShowDelete(false)}
    >
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-accent-red/10 flex items-center justify-center border border-accent-red/20">
            <Video className="w-5 h-5 text-accent-red" />
          </div>
          <div>
            <h3 className="font-medium text-text-primary group-hover:text-accent-red transition-colors">
              {project.name}
            </h3>
            <p className="text-xs text-text-muted mt-0.5">
              {formatDate(project.modified_at)}
            </p>
          </div>
        </div>

        <AnimatePresence>
          {showDelete && (
            <motion.button
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.8 }}
              onClick={(e) => {
                e.stopPropagation()
                onDelete()
              }}
              className="p-2 rounded-md hover:bg-accent-red/20 text-text-muted hover:text-accent-red transition-colors"
            >
              <Trash2 className="w-4 h-4" />
            </motion.button>
          )}
        </AnimatePresence>
      </div>

      <div className="mt-4 flex items-center gap-4 text-xs text-text-muted">
        <div className="flex items-center gap-1.5">
          <Video className="w-3.5 h-3.5" />
          <span>{project.video_count} video{project.video_count !== 1 ? 's' : ''}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <FileText className="w-3.5 h-3.5" />
          <span>{project.segments_count} segment{project.segments_count !== 1 ? 's' : ''}</span>
        </div>
      </div>

      <div className="mt-3 flex items-center text-xs text-accent-red opacity-0 group-hover:opacity-100 transition-opacity">
        <span>Open project</span>
        <ChevronRight className="w-4 h-4 ml-1" />
      </div>
    </motion.div>
  )
}

function CreateProjectModal({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const [projectName, setProjectName] = useState('')
  const [uploadedVideos, setUploadedVideos] = useState<{ path: string; name: string }[]>([])
  const [isUploading, setIsUploading] = useState(false)
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  const createMutation = useMutation({
    mutationFn: () =>
      projectsApi.create(projectName, uploadedVideos.map((v) => v.path)),
    onSuccess: () => {
      toast.success('Project created successfully!')
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      navigate(`/project/${projectName}`)
      onClose()
    },
    onError: (error: Error) => {
      toast.error(`Failed to create project: ${error.message}`)
    },
  })

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files) return

    setIsUploading(true)
    try {
      for (const file of Array.from(files)) {
        const response = await videosApi.upload(file)
        setUploadedVideos((prev) => [
          ...prev,
          { path: response.data.path, name: file.name },
        ])
      }
      toast.success(`${files.length} video(s) uploaded`)
    } catch (error) {
      toast.error('Failed to upload video')
    } finally {
      setIsUploading(false)
    }
  }

  const removeVideo = (index: number) => {
    setUploadedVideos((prev) => prev.filter((_, i) => i !== index))
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="relative bg-terminal-surface border border-terminal-border rounded-lg w-full max-w-lg mx-4 overflow-hidden"
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-terminal-border">
          <div className="flex items-center gap-2">
            <FolderPlus className="w-5 h-5 text-accent-red" />
            <h2 className="font-medium">Create New Project</h2>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded hover:bg-terminal-elevated text-text-muted hover:text-text-primary"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-4 space-y-4">
          {/* Project name */}
          <div>
            <label className="section-header">Project Name</label>
            <input
              type="text"
              value={projectName}
              onChange={(e) => setProjectName(e.target.value)}
              placeholder="My Awesome Project"
              className="input-base w-full"
              autoFocus
            />
          </div>

          {/* Video upload */}
          <div>
            <label className="section-header">Videos</label>
            <div
              className={clsx(
                'border-2 border-dashed rounded-lg p-6 text-center transition-colors',
                'border-terminal-border hover:border-accent-red/50'
              )}
            >
              <input
                type="file"
                accept="video/*"
                multiple
                onChange={handleFileUpload}
                className="hidden"
                id="video-upload"
                disabled={isUploading}
              />
              <label
                htmlFor="video-upload"
                className="cursor-pointer flex flex-col items-center gap-2"
              >
                {isUploading ? (
                  <Loader2 className="w-8 h-8 text-accent-red animate-spin" />
                ) : (
                  <Upload className="w-8 h-8 text-text-muted" />
                )}
                <span className="text-sm text-text-muted">
                  {isUploading ? 'Uploading...' : 'Click to upload videos'}
                </span>
                <span className="text-xs text-text-disabled">
                  MP4, MOV, AVI, MKV, WEBM
                </span>
              </label>
            </div>

            {/* Uploaded videos list */}
            {uploadedVideos.length > 0 && (
              <div className="mt-3 space-y-2">
                {uploadedVideos.map((video, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between bg-terminal-elevated rounded-md px-3 py-2"
                  >
                    <div className="flex items-center gap-2">
                      <Video className="w-4 h-4 text-accent-red" />
                      <span className="text-sm truncate max-w-[200px]">{video.name}</span>
                    </div>
                    <button
                      onClick={() => removeVideo(i)}
                      className="p-1 rounded hover:bg-terminal-border text-text-muted hover:text-accent-red"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 p-4 border-t border-terminal-border bg-terminal-bg/50">
          <button onClick={onClose} className="btn-secondary">
            Cancel
          </button>
          <button
            onClick={() => createMutation.mutate()}
            disabled={!projectName || uploadedVideos.length === 0 || createMutation.isPending}
            className="btn-primary flex items-center gap-2"
          >
            {createMutation.isPending && <Loader2 className="w-4 h-4 animate-spin" />}
            Create Project
          </button>
        </div>
      </motion.div>
    </div>
  )
}

export default function HomePage() {
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null)
  const queryClient = useQueryClient()

  const { data: projects, isLoading } = useQuery({
    queryKey: ['projects'],
    queryFn: () => projectsApi.list(),
  })

  const deleteMutation = useMutation({
    mutationFn: (name: string) => projectsApi.delete(name),
    onSuccess: () => {
      toast.success('Project deleted')
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      setDeleteConfirm(null)
    },
    onError: () => {
      toast.error('Failed to delete project')
    },
  })

  const projectList: ProjectListItem[] = projects?.data || []

  return (
    <div className="max-w-6xl mx-auto p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold">Projects</h1>
          <p className="text-text-muted text-sm mt-1">
            Manage your voice-over dubbing projects
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="btn-primary flex items-center gap-2"
        >
          <FolderPlus className="w-4 h-4" />
          New Project
        </button>
      </div>

      {/* Projects grid */}
      {isLoading ? (
        <div className="flex items-center justify-center h-64">
          <Loader2 className="w-8 h-8 text-accent-red animate-spin" />
        </div>
      ) : projectList.length === 0 ? (
        <div className="console-card p-12 text-center">
          <Video className="w-12 h-12 text-text-muted mx-auto mb-4" />
          <h3 className="text-lg font-medium mb-2">No projects yet</h3>
          <p className="text-text-muted text-sm mb-6">
            Create your first project to start adding voice-overs to your videos
          </p>
          <button
            onClick={() => setShowCreateModal(true)}
            className="btn-primary inline-flex items-center gap-2"
          >
            <FolderPlus className="w-4 h-4" />
            Create Your First Project
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <AnimatePresence>
            {projectList.map((project) => (
              <ProjectCard
                key={project.name}
                project={project}
                onDelete={() => setDeleteConfirm(project.name)}
              />
            ))}
          </AnimatePresence>
        </div>
      )}

      {/* Create modal */}
      <CreateProjectModal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
      />

      {/* Delete confirmation */}
      <AnimatePresence>
        {deleteConfirm && (
          <div className="fixed inset-0 z-50 flex items-center justify-center">
            <div
              className="absolute inset-0 bg-black/60"
              onClick={() => setDeleteConfirm(null)}
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="relative bg-terminal-surface border border-terminal-border rounded-lg p-6 max-w-sm mx-4"
            >
              <h3 className="font-medium mb-2">Delete Project?</h3>
              <p className="text-sm text-text-muted mb-4">
                Are you sure you want to delete "{deleteConfirm}"? This action cannot be undone.
              </p>
              <div className="flex justify-end gap-2">
                <button
                  onClick={() => setDeleteConfirm(null)}
                  className="btn-secondary"
                >
                  Cancel
                </button>
                <button
                  onClick={() => deleteMutation.mutate(deleteConfirm)}
                  disabled={deleteMutation.isPending}
                  className="btn-primary bg-red-600 hover:bg-red-500"
                >
                  {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  )
}
