import { QuartzComponent, QuartzComponentConstructor, QuartzComponentProps } from "./types"

/**
 * Categories with a designed look. The vault contains many older values
 * (Entity, Group: *, Region: *, the various List types) which are legacy
 * and deliberately render nothing until they are re-planned.
 */
const labels: Record<string, string> = {
  Community: "🏙 Community",
  Realm: "👑 Realm",
}

const CategoryBadge: QuartzComponent = ({ fileData }: QuartzComponentProps) => {
  const frontmatter = fileData.frontmatter as Record<string, unknown> | undefined
  const raw = frontmatter?.Category ?? frontmatter?.category

  if (typeof raw !== "string") {
    return null
  }

  const category = raw.trim()
  const label = labels[category]

  if (!label) {
    return null
  }

  return (
    <div className="category-badge" data-category={category}>
      {label}
    </div>
  )
}

CategoryBadge.css = `
.category-badge {
  display: inline-block;
  margin-bottom: 1rem;
  padding: 0.3rem 0.8rem;
  border-left: 3px solid var(--cont-accent, #b59b5a);
  color: var(--darkgray);
  font-size: 0.9rem;
  font-weight: 600;
  letter-spacing: 0.05em;
}
`

export default (() => CategoryBadge) satisfies QuartzComponentConstructor
