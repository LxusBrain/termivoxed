import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import DOMPurify from 'dompurify'

/**
 * Configure DOMPurify for secure HTML sanitization.
 * Uses industry-standard library instead of custom implementation.
 * Prevents XSS attacks including SVG-based, data URI, and event handler attacks.
 */
const sanitizeHtml = (html: string): string => {
  return DOMPurify.sanitize(html, {
    // Remove dangerous tags
    FORBID_TAGS: ['script', 'iframe', 'frame', 'object', 'embed', 'applet', 'form'],
    // Remove dangerous attributes
    FORBID_ATTR: ['onerror', 'onload', 'onclick', 'onmouseover', 'onfocus', 'onblur'],
    // Allow safe URI schemes only
    ALLOWED_URI_REGEXP: /^(?:(?:https?|mailto|tel):|[^a-z]|[a-z+.\-]+(?:[^a-z+.\-:]|$))/i,
    // Prevent data: URIs with executable content
    ADD_TAGS: ['style'],
    ADD_ATTR: ['target'],
    // Return string, not DOM node
    RETURN_DOM: false,
    RETURN_DOM_FRAGMENT: false,
  })
}

// Map of legal document types to their HTML files
const LEGAL_DOCUMENTS: Record<string, { title: string; path: string }> = {
  terms: {
    title: 'Terms & Conditions',
    path: '/legal/terms-of-service.html'
  },
  privacy: {
    title: 'Privacy Policy',
    path: '/legal/privacy-policy.html'
  },
  refund: {
    title: 'Cancellation & Refund',
    path: '/legal/refund-policy.html'
  },
  shipping: {
    title: 'Shipping & Delivery',
    path: '/legal/shipping.html'
  },
  contact: {
    title: 'Contact Us',
    path: '/legal/contact.html'
  }
}

export default function LegalPage() {
  const { type } = useParams<{ type: string }>()
  const [content, setContent] = useState<string>('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const document = type ? LEGAL_DOCUMENTS[type] : null

  useEffect(() => {
    if (!document) {
      setError('Document not found')
      setLoading(false)
      return
    }

    fetch(document.path)
      .then((res) => {
        if (!res.ok) throw new Error('Failed to load document')
        return res.text()
      })
      .then((html) => {
        // Sanitize HTML content to prevent XSS attacks
        const sanitizedContent = sanitizeHtml(html)
        setContent(sanitizedContent)
        setLoading(false)
      })
      .catch((err) => {
        setError(err.message)
        setLoading(false)
      })
  }, [document])

  if (!document) {
    return (
      <div className="min-h-screen bg-gray-900 text-white flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold mb-4">Document Not Found</h1>
          <p className="text-gray-400 mb-4">The requested legal document does not exist.</p>
          <Link to="/" className="text-purple-400 hover:underline">
            Return to Home
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-900">
      {/* Header */}
      <header className="bg-gray-800 border-b border-gray-700 sticky top-0 z-10">
        <div className="max-w-4xl mx-auto px-4 py-4 flex items-center justify-between">
          <Link to="/" className="flex items-center space-x-2">
            <span className="text-2xl font-bold bg-gradient-to-r from-purple-400 to-pink-500 bg-clip-text text-transparent">
              TermiVoxed
            </span>
          </Link>
          <nav className="flex items-center space-x-4">
            <Link to="/login" className="text-gray-400 hover:text-white">
              Login
            </Link>
            <Link
              to="/signup"
              className="px-4 py-2 bg-purple-600 hover:bg-purple-700 rounded-lg text-white"
            >
              Sign Up
            </Link>
          </nav>
        </div>
      </header>

      {/* Legal document navigation */}
      <div className="bg-gray-800 border-b border-gray-700">
        <div className="max-w-4xl mx-auto px-4 py-3">
          <nav className="flex flex-wrap gap-4">
            {Object.entries(LEGAL_DOCUMENTS).map(([key, doc]) => (
              <Link
                key={key}
                to={`/legal/${key}`}
                className={`text-sm ${
                  type === key
                    ? 'text-purple-400 font-semibold'
                    : 'text-gray-400 hover:text-white'
                }`}
              >
                {doc.title}
              </Link>
            ))}
          </nav>
        </div>
      </div>

      {/* Content */}
      <main className="max-w-4xl mx-auto px-4 py-8">
        {loading && (
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-purple-500"></div>
          </div>
        )}

        {error && (
          <div className="bg-red-900/50 border border-red-700 rounded-lg p-4">
            <p className="text-red-400">{error}</p>
          </div>
        )}

        {!loading && !error && (
          <div
            className="prose prose-invert prose-purple max-w-none
                       prose-headings:text-white prose-p:text-gray-300
                       prose-a:text-purple-400 prose-strong:text-white
                       prose-li:text-gray-300"
            dangerouslySetInnerHTML={{ __html: content }}
          />
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-700 py-8 mt-12">
        <div className="max-w-4xl mx-auto px-4 text-center text-gray-500 text-sm">
          <p>&copy; {new Date().getFullYear()} LXUSBrain. All rights reserved.</p>
          <p className="mt-2">
            <a href="mailto:support@luxusbrain.com" className="text-purple-400 hover:underline">
              support@luxusbrain.com
            </a>
          </p>
        </div>
      </footer>
    </div>
  )
}
