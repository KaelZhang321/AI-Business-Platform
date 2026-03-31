import { theme } from '../../styles/theme'

export const chartPalette = theme.chartPalette

export const baseOption = {
  backgroundColor: 'transparent',
  textStyle: { fontFamily: theme.fontFamily, color: theme.colors.textSecondary },
  tooltip: {
    backgroundColor: 'rgba(6, 18, 46, 0.94)',
    borderColor: 'rgba(121, 231, 255, 0.22)',
    borderWidth: 1,
    textStyle: { color: '#f2f8ff', fontSize: 12, fontFamily: theme.fontFamily },
    extraCssText: 'backdrop-filter:blur(22px);-webkit-backdrop-filter:blur(22px);box-shadow:0 10px 36px rgba(0,0,0,0.54),0 0 14px rgba(121,231,255,0.1);border-radius:10px;padding:10px 14px;',
  },
  legend: {
    right: 0,
    textStyle: { color: '#a6bbdc', fontSize: 11, fontFamily: theme.fontFamily },
    icon: 'roundRect',
    itemWidth: 12,
    itemHeight: 3,
    itemGap: 16,
  },
  grid: { left: 56, right: 24, top: 40, bottom: 36, containLabel: false },
}

export const axisStyle = {
  axisLine: { lineStyle: { color: 'rgba(121,231,255,0.1)' } },
  axisTick: { show: false },
  axisLabel: { color: '#90aad1', fontSize: 11, fontFamily: theme.fontFamily },
  splitLine: { lineStyle: { color: 'rgba(121,231,255,0.05)', type: 'dashed' as const } },
}
