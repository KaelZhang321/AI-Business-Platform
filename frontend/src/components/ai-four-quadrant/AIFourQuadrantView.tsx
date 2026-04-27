import { useMemo } from 'react'
import TargetCursor from './TargetCursor'
import { FourQuadrantHeader, QuadrantWorkspace, ResultSidebar, SelectionPanel, StatusBanner } from './components'
import { useFourQuadrantState } from './useFourQuadrantState'
import type { AIFourQuadrantViewProps } from './types'
import { useLocation } from 'react-router-dom'

export const AIFourQuadrantView = ({
  setCurrentPage,
  isDarkMode,
  setIsDarkMode,
  hideHeader = false,
  navigationParams,
}: AIFourQuadrantViewProps) => {
  const location = useLocation()
  const urlParams = new URLSearchParams(location.search)
  const customerNameFromUrl = urlParams.get('customerName')?.trim() || ''

  const mergedNavigationParams = useMemo(
    () => ({
      ...navigationParams,
      ...(customerNameFromUrl ? { customerName: customerNameFromUrl } : {}),
    }),
    [navigationParams, customerNameFromUrl],
  )

  const {
    selectedClientId,
    setSelectedClientId,
    selectedReportId,
    setSelectedReportId,
    notes,
    setNotes,
    customerKeyword,
    setCustomerKeyword,
    isClientDropdownOpen,
    setIsClientDropdownOpen,
    isReportDropdownOpen,
    setIsReportDropdownOpen,
    isAnalyzing,
    isLoadingReports,
    showResults,
    isEnlarged,
    setIsEnlarged,
    chatMessages,
    chatInput,
    setChatInput,
    quadrantData,
    setQuadrantData,
    clients,
    isLoadingClients,
    isLoadingMoreClients,
    hasMoreClients,
    loadMoreClients,
    selectedClient,
    availableReports,
    selectedReport,
    analysisProgress,
    analysisStep,
    handleStartAnalysis,
    handleSendMessage,
    handleConfirmQuadrants,
  } = useFourQuadrantState(mergedNavigationParams)

  return (
    <div className="space-y-6 pb-12 h-full flex flex-col relative">
      <TargetCursor targetSelector=".cursor-target" containerSelector=".quadrants-container" />

      <FourQuadrantHeader
        hideHeader={hideHeader}
        selectedClient={selectedClient}
        isDarkMode={isDarkMode}
        setIsDarkMode={setIsDarkMode}
        setCurrentPage={setCurrentPage}
      />

      <div className={`px-8 flex gap-6 flex-1 items-stretch overflow-hidden ${hideHeader ? 'pt-8' : ''}`}>
        <div className="w-[360px] shrink-0 flex flex-col">
          <div className="bg-white dark:bg-slate-800 rounded-2xl p-6 shadow-sm border border-slate-100 dark:border-slate-700 h-full flex flex-col">
            {!showResults ? (
              <SelectionPanel
                selectedClient={selectedClient}
                selectedClientId={selectedClientId}
                selectedReport={selectedReport}
                selectedReportId={selectedReportId}
                availableReports={availableReports}
                notes={notes}
                isClientDropdownOpen={isClientDropdownOpen}
                isReportDropdownOpen={isReportDropdownOpen}
                isAnalyzing={isAnalyzing || isLoadingClients}
                isLoadingReports={isLoadingReports}
                clients={clients}
                isLoadingMoreClients={isLoadingMoreClients}
                isLoadingClients={isLoadingClients}
                hasMoreClients={hasMoreClients}
                customerKeyword={customerKeyword}
                onClientDropdownToggle={() => setIsClientDropdownOpen((prev) => !prev)}
                onReportDropdownToggle={() => setIsReportDropdownOpen((prev) => !prev)}
                onSelectClient={(id) => {
                  const target = clients.find((item) => item.id === id)
                  setSelectedClientId(id)
                  setCustomerKeyword(target?.name ?? '')
                  setIsClientDropdownOpen(false)
                }}
                onLoadMoreClients={loadMoreClients}
                onCustomerKeywordChange={setCustomerKeyword}
                onSelectReport={(id) => {
                  setSelectedReportId(id)
                  setIsReportDropdownOpen(false)
                }}
                onSetNotes={setNotes}
                onStartAnalysis={handleStartAnalysis}
              />
            ) : (
              <ResultSidebar
                analysis={{
                  monitoring: [],
                  intervention: [],
                  maintenance: [],
                  prevention: [],
                  conclusion: '',
                  clientInfo: '',
                  reportInfo: '',
                  riskLevel: '',
                  score: 0,
                }}
                selectedClient={selectedClient}
                selectedReport={selectedReport}
                chatMessages={chatMessages}
                chatInput={chatInput}
                onChatInputChange={setChatInput}
                onSendMessage={handleSendMessage}
              />
            )}
          </div>
        </div>

        <div className="flex-1 flex flex-col space-y-6">
          <StatusBanner
            showResults={showResults}
            isAnalyzing={isAnalyzing}
            selectedClientId={selectedClientId}
            selectedReportId={selectedReportId}
            selectedClient={selectedClient}
            selectedReport={selectedReport}
            notes={notes}
            analysisProgress={analysisProgress}
            analysisStep={analysisStep}
          />

          <QuadrantWorkspace
            showResults={showResults}
            isAnalyzing={isAnalyzing}
            isEnlarged={isEnlarged}
            setIsEnlarged={setIsEnlarged}
            quadrantData={quadrantData}
            setQuadrantData={setQuadrantData}
            analysisStep={analysisStep}
            analysisProgress={analysisProgress}
            onQuadrantAddItem={({ nextData }) => {
              void handleConfirmQuadrants(nextData)
            }}
          />
        </div>
      </div>
    </div>
  )
}
