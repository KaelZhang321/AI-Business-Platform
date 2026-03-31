import { useQuery } from '@tanstack/react-query'
import { fetchKpiOverview } from '../api/kpi'
import { fetchRegistrationChart, fetchRegistrationMatrix } from '../api/registration'
import { fetchCustomerProfile } from '../api/customer'
import { fetchSourceDistribution, fetchTargetArrival } from '../api/source'
import { fetchOperationsKpi, fetchTrendData } from '../api/operations'
import { fetchAchievementChart, fetchAchievementTable } from '../api/achievement'
import { fetchProgress } from '../api/progress'
import { fetchProposalOverview, fetchProposalCrossTable } from '../api/proposal'

export const useKpiOverview = () =>
  useQuery({ queryKey: ['kpi-overview'], queryFn: fetchKpiOverview })

export const useRegistrationChart = () =>
  useQuery({ queryKey: ['registration-chart'], queryFn: fetchRegistrationChart })

export const useRegistrationMatrix = () =>
  useQuery({ queryKey: ['registration-matrix'], queryFn: fetchRegistrationMatrix })

export const useCustomerProfile = () =>
  useQuery({ queryKey: ['customer-profile'], queryFn: fetchCustomerProfile })

export const useSourceDistribution = () =>
  useQuery({ queryKey: ['source-distribution'], queryFn: fetchSourceDistribution })

export const useTargetArrival = () =>
  useQuery({ queryKey: ['target-arrival'], queryFn: fetchTargetArrival })

export const useOperationsKpi = (dateFrom?: string, dateTo?: string) =>
  useQuery({
    queryKey: ['operations-kpi', dateFrom, dateTo],
    queryFn: () => fetchOperationsKpi(dateFrom, dateTo),
  })

export const useTrendData = () =>
  useQuery({ queryKey: ['trend-data'], queryFn: fetchTrendData })

export const useAchievementChart = () =>
  useQuery({ queryKey: ['achievement-chart'], queryFn: fetchAchievementChart })

export const useAchievementTable = () =>
  useQuery({ queryKey: ['achievement-table'], queryFn: fetchAchievementTable })

export const useProgress = () =>
  useQuery({ queryKey: ['progress'], queryFn: fetchProgress })

export const useProposalOverview = () =>
  useQuery({ queryKey: ['proposal-overview'], queryFn: fetchProposalOverview })

export const useProposalCrossTable = () =>
  useQuery({ queryKey: ['proposal-cross-table'], queryFn: fetchProposalCrossTable })
