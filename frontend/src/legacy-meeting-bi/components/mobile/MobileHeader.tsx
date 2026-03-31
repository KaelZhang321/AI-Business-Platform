import React from 'react'
import dayjs from 'dayjs'
import eventLogo from '../../styles/logo.png'

const MobileHeader: React.FC = () => {
  const updateTime = dayjs().format('YYYY-MM-DD HH:mm:ss')

  return (
    <div className="mobile-header">
      <div className="mobile-header-row">
        <div className="mobile-header-brand">
          <div className="mobile-header-title">318梅赛尔国际健康节</div>
          <div className="mobile-header-time">{updateTime}</div>
        </div>
        <img className="mobile-header-logo" src={eventLogo} alt="318梅赛尔国际健康节 Logo" />
      </div>
    </div>
  )
}

export default MobileHeader
