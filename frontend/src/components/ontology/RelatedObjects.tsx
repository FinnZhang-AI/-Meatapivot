import { Link } from 'react-router-dom'
import type { OntologyLink } from '../../types/ontology'

interface Props {
  objectId: string
  links: OntologyLink[]
  onDeleteLink?: (linkId: string) => void
  isDeleting?: boolean
}

export default function RelatedObjects({ objectId, links, onDeleteLink, isDeleting }: Props) {
  const grouped = links.reduce((acc, link) => {
    const type = link.linkTypeName || 'unknown'
    if (!acc[type]) acc[type] = []
    acc[type].push(link)
    return acc
  }, {} as Record<string, OntologyLink[]>)

  return (
    <div className="space-y-4">
      {Object.entries(grouped).map(([typeName, typeLinks]) => (
        <div key={typeName}>
          <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">{typeName}</h4>
          <div className="space-y-2">
            {typeLinks.map((link) => {
              const isSource = link.sourceObjectId === objectId
              const targetId = isSource ? link.targetObjectId : link.sourceObjectId
              return (
                <div key={link.id} className="flex items-center gap-2 group">
                  <Link
                    to={`/objects/${link.targetObjectType || 'unknown'}/${targetId}`}
                    className="flex-1 flex items-center gap-2 p-2 rounded-lg bg-slate-50 dark:bg-slate-700/50 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
                  >
                    <span className="text-xs text-slate-400">{isSource ? '→' : '←'}</span>
                    <span className="text-sm font-medium">{link.targetObjectKey || targetId.slice(0, 8)}</span>
                    <span className="text-xs text-slate-500">{link.targetObjectType}</span>
                  </Link>
                  {onDeleteLink && (
                    <button
                      onClick={() => onDeleteLink(link.id)}
                      disabled={isDeleting}
                      className="opacity-0 group-hover:opacity-100 p-1.5 text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-all disabled:opacity-50"
                      title="删除此关系"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      ))}
      {links.length === 0 && <div className="text-center text-slate-400 py-4">暂无关联对象</div>}
    </div>
  )
}
