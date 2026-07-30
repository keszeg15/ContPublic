import { QuartzComponent, QuartzComponentConstructor, QuartzComponentProps } from "./types"

const CategoryBadge: QuartzComponent = ({ fileData }: QuartzComponentProps) => {
  const category = fileData.frontmatter?.category

  if (!category) {
    return null
  }

  const labels: Record<string, string> = {
    Community: "🏙 Community",
    Realm: "👑 Realm",
    Terrain: "⛰ Terrain",
  }

  return (
    <div className="category-badge">
      {labels[category] ?? category}
    </div>
  )
}

CategoryBadge.css = `
.category-badge {
  display: inline-block;
  margin-bottom: 1rem;
  padding: 0.3rem 0.8rem;
  border-left: 3px solid #b59b5a;
  color: #6b5a35;
  font-size: 0.9rem;
  font-weight: 600;
  letter-spacing: 0.05em;
}
`

export default (() => CategoryBadge) satisfies QuartzComponentConstructor
