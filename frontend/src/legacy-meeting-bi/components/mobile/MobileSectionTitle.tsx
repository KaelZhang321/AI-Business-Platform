import React from 'react'

interface MobileSectionTitleProps {
  title?: string
  subtitle?: string
  accentColor?: string
}

const MobileSectionTitle: React.FC<MobileSectionTitleProps> = ({
  title,
  subtitle,
  accentColor = '#3B82F6',
}) => (
  <div className="mobile-section-title">
    <div
      className="mobile-section-title__bar"
      style={{ background: accentColor }}
    />
    <div>
      {title && <div className="mobile-section-title__text">{title}</div>}
      {subtitle && <div className="mobile-section-title__sub">{subtitle}</div>}
    </div>
  </div>
)

export default MobileSectionTitle
