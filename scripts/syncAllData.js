import { fetchMarketData } from './fetchMarketData.js';
import { syncEmotionIndicators } from './syncEmotionIndicators.js';
import { syncKlineLibraryPy } from './syncKlineLibraryPy.js';
import { syncStockCompany } from './syncStockCompany.js';
import { syncSentimentCycleSnapshotsPy } from './syncSentimentCycleSnapshotsPy.js';
import { syncSectorSnapshotsPy } from './syncSectorSnapshotsPy.js';
import {
  getOrCreateSyncContext,
  printStageSummary,
  readJsonFile,
  runStagesSequentially,
} from './syncUtils.js';

export const syncAllData = async () => {
  const continueOnError = process.env.SYNC_CONTINUE_ON_ERROR !== '0';
  const summary = await runStagesSequentially([
    { key: 'market-pipeline', name: 'Market Data Pipeline', run: fetchMarketData, retries: 1 },
    {
      key: 'kline-library',
      name: 'K-Line Library (tushare)',
      run: syncKlineLibraryPy,
      retries: 1,
    },
    {
      key: 'stock-company',
      name: 'Stock Company Info (tushare)',
      run: syncStockCompany,
      retries: 1,
    },
    {
      key: 'cycle',
      name: 'Sentiment Cycle Snapshots (tushare)',
      run: syncSentimentCycleSnapshotsPy,
      retries: 1,
      shouldRun: async (context) => {
        const leaderState = await readJsonFile('leader_state.json');
        const latestCycle = Array.isArray(leaderState) ? leaderState.at(-1)?.date : null;
        return latestCycle === context.onlineMonthDay
          ? `already up-to-date (${context.onlineMonthDay})`
          : true;
      },
    },
    {
      key: 'sectors',
      name: 'Sector Snapshots (tushare)',
      run: syncSectorSnapshotsPy,
      retries: 1,
      shouldRun: async (context) => {
        const rotation = await readJsonFile('sector_rotation_concept.json');
        const latestDate = rotation?.dates?.[0] ?? null;
        return latestDate === context.onlineMonthDay
          ? `already up-to-date (${context.onlineMonthDay})`
          : true;
      },
    },
    {
      key: 'emotion',
      name: 'Emotion Indicators (tushare)',
      run: syncEmotionIndicators,
      retries: 1,
      shouldRun: async (context) => {
        const emotion = await readJsonFile('emotion_indicators.json');
        const latestEmotion = Array.isArray(emotion) ? emotion.at(-1)?.date : null;
        return latestEmotion === context.emotionTargetDate
          ? `already up-to-date (${context.emotionTargetDate})`
          : true;
      },
    },
  ], {
    resolveContext: getOrCreateSyncContext,
    continueOnError,
    printSummary: true,
    printSummaryOnError: true,
    summaryLabel: 'sync:all',
    writeStatus: true,
  });

  const failed = summary.filter((item) => item.status === 'failed');
  if (failed.length) {
    printStageSummary(summary, 'sync:all');
    throw new Error(`sync:all completed with ${failed.length} failed stage(s)`);
  }
};

syncAllData().catch((error) => {
  console.error('[sync-all] Failed to sync all data:', error);
  process.exitCode = 1;
});
