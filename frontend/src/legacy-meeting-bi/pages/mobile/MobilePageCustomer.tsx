import React from 'react'
import MobileRegistrationSection from '../../components/mobile/sections/MobileRegistrationSection'
import MobileCustomerProfileSection from '../../components/mobile/sections/MobileCustomerProfileSection'
import MobileCustomerSourceSection from '../../components/mobile/sections/MobileCustomerSourceSection'

const MobilePageCustomer: React.FC = () => (
  <div>
    <div className="mobile-section">
      <MobileRegistrationSection />
    </div>
    <div className="mobile-section">
      <MobileCustomerProfileSection />
    </div>
    <div className="mobile-section">
      <MobileCustomerSourceSection />
    </div>
  </div>
)

export default MobilePageCustomer
