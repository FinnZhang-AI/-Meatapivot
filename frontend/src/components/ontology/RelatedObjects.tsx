import { Link } from 'react-router-dom'
import type { OntologyLink } from '../../types/ontology'

interface Props {
  objectId: string
  links: OntologyLink[]
}

export default function RelatedObjects({ objectId, links }: Props) {
  // Group by link type
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
                <Link
                  key={link.id}
                  to={`/objects/${link.targetObjectType || 'unknown'}/${targetId}`}
                  className="flex items-center gap-2 p-2 rounded-lg bg-slate-50 dark:bg-slate-700/50 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
                >
                  <span className="text-xs text-slate-400">{isSource ? '→' : '←'}</span>
                  <span className="text-sm font-medium">{link.targetObjectKey || targetId.slice(0, 8)}</span>
                  <span className="text-xs text-slate-500">{link.targetObjectType}</span>
                </Link>
              )
            })}
          </div>
        </div>
      ))}
      {links.length === 0 && <div className="text-center text-slate-400 py-4">暂无关联对象</div>}
    </div>
  )
}
