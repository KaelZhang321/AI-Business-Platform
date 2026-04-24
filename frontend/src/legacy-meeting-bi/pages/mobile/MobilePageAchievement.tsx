import React from 'react'
import MobileAchievementSection from '../../components/mobile/sections/MobileAchievementSection'
import MobileProgressSection from '../../components/mobile/sections/MobileProgressSection'
import MobileProposalSection from '../../components/mobile/sections/MobileProposalSection'

const MobilePageAchievement: React.FC = () => (
  <div>
    <div className="mobile-section">
      <MobileAchievementSection />
    </div>
    <div className="mobile-section">
      <MobileProgressSection />
    </div>
    <div className="mobile-section">
      <MobileProposalSection />
    </div>
  </div>
)

export default MobilePageAchievement
