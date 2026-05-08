package com.lzke.ai.service;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Java version of the Python L1RuleCleaner.
 *
 * It only performs deterministic L1 cleaning and exact dictionary lookup:
 * trim -> remove star prefix -> full-width punctuation normalization ->
 * bracket abbreviation extraction -> unit suffix removal -> trailing punctuation
 * removal -> internal Chinese-space removal -> dictionary lookup.
 */
public final class L1RuleCleaner {
    private static final Pattern BRACKET_ABBR_PATTERN = Pattern.compile("^(.+?)\\(([A-Za-z0-9\\-\\.βⅢ\\s]+)\\)$");
    private static final Pattern UNIT_SUFFIX_PATTERN = Pattern.compile("^(.+?)\\(([^()]+)\\)$");
    private static final Pattern CHINESE_INTERNAL_SPACE_PATTERN = Pattern.compile("([\\u4e00-\\u9fff])\\s+([\\u4e00-\\u9fff])");
    private static final Pattern TRAILING_PUNCTUATION_PATTERN = Pattern.compile("[\\.。,，、\\-_/]+$");

    private static final Set<String> UNIT_SUFFIXES = new HashSet<String>(Arrays.asList(
        "mmol/L",
        "mg/dl",
        "mg/dL",
        "g/L",
        "U/L",
        "IU/mL",
        "ng/mL",
        "pg/mL",
        "kg",
        "cm",
        "%"
    ));

    private static volatile MapLookupProvider defaultLookupProvider;

    private L1RuleCleaner() {
    }

    /**
     * Load data/standard_dict.csv and data/alias_dict.csv from the project root once.
     * Call this during application startup.
     */
    public static void initializeOnce(Path projectRoot) throws IOException {
        initializeOnce(projectRoot.resolve("data/standard_dict.csv"), projectRoot.resolve("data/alias_dict.csv"));
    }

    /**
     * Load dictionary CSV files once. Repeated calls are ignored.
     */
    public static void initializeOnce(Path standardDictPath, Path aliasDictPath) throws IOException {
        if (defaultLookupProvider != null) {
            return;
        }
        synchronized (L1RuleCleaner.class) {
            if (defaultLookupProvider == null) {
                defaultLookupProvider = loadFromCsv(standardDictPath, aliasDictPath);
            }
        }
    }

    /**
     * Load dictionary CSV streams once. This works both in IDE and packaged jar runtime.
     */
    public static void initializeOnce(InputStream standardDictInputStream, InputStream aliasDictInputStream) throws IOException {
        if (defaultLookupProvider != null) {
            return;
        }
        synchronized (L1RuleCleaner.class) {
            if (defaultLookupProvider == null) {
                defaultLookupProvider = loadFromCsv(standardDictInputStream, aliasDictInputStream);
            }
        }
    }

    /**
     * Force reload dictionary CSV files. Use this only for admin refresh or tests.
     */
    public static synchronized void reload(Path standardDictPath, Path aliasDictPath) throws IOException {
        defaultLookupProvider = loadFromCsv(standardDictPath, aliasDictPath);
    }

    public static boolean isInitialized() {
        return defaultLookupProvider != null;
    }

    public static CleanResult clean(String itemName) {
        return clean(itemName, getDefaultLookupProvider());
    }

    public static List<CleanResult> cleanBatch(List<String> itemNames) {
        return cleanBatch(itemNames, getDefaultLookupProvider());
    }

    public static MapLookupProvider loadFromCsv(Path standardDictPath, Path aliasDictPath) throws IOException {
        List<Map<String, String>> standardRows = readCsv(standardDictPath);
        List<Map<String, String>> aliasRows = readCsv(aliasDictPath);
        return buildLookupProvider(standardRows, aliasRows);
    }

    public static MapLookupProvider loadFromCsv(InputStream standardDictInputStream, InputStream aliasDictInputStream) throws IOException {
        List<Map<String, String>> standardRows = readCsv(standardDictInputStream);
        List<Map<String, String>> aliasRows = readCsv(aliasDictInputStream);
        return buildLookupProvider(standardRows, aliasRows);
    }

    private static MapLookupProvider buildLookupProvider(
        List<Map<String, String>> standardRows,
        List<Map<String, String>> aliasRows
    ) {
        Map<String, LookupPayload> codeToPayload = new HashMap<String, LookupPayload>();
        MapLookupProvider provider = new MapLookupProvider();

        for (Map<String, String> row : standardRows) {
            String code = row.get("code");
            String standardName = row.get("standard_name");
            String category = row.get("category");
            if (isBlank(code) || isBlank(standardName)) {
                continue;
            }

            LookupPayload payload = new LookupPayload(code.trim(), standardName.trim(), trimToEmpty(category));
            codeToPayload.put(code.trim(), payload);

            provider.registerStandard(standardName, row.get("abbreviation"), payload);
            for (String alias : splitAliases(row.get("aliases"))) {
                provider.registerAlias(alias, payload);
            }
        }

        for (Map<String, String> row : aliasRows) {
            String alias = row.get("alias");
            String standardCode = row.get("standard_code");
            if (isBlank(alias) || isBlank(standardCode)) {
                continue;
            }

            LookupPayload payload = codeToPayload.get(standardCode.trim());
            if (payload != null) {
                provider.registerAlias(alias, payload);
            }
        }

        return provider;
    }

    public static CleanResult clean(String itemName, LookupProvider dictManager) {
        String original = itemName == null ? "" : itemName;
        String cleaned = strip(original);
        cleaned = removeStarPrefix(cleaned);
        cleaned = fullWidthToHalfWidth(cleaned);

        BracketResult bracketResult = extractAbbreviationFromBrackets(cleaned);
        cleaned = bracketResult.cleanedName;
        String abbreviation = bracketResult.abbreviation;

        if (abbreviation == null) {
            cleaned = removeUnitSuffix(cleaned);
        }
        cleaned = removeTrailingPunctuation(cleaned);
        cleaned = removeInternalSpaces(cleaned);

        LookupPayload lookup = dictManager == null ? null : dictManager.lookup(cleaned, abbreviation);
        if (lookup != null) {
            String matchSource = abbreviation != null && abbreviation.toUpperCase(Locale.ROOT).equals(cleaned.toUpperCase(Locale.ROOT))
                ? "abbr_exact"
                : "alias_exact";
            return new CleanResult(
                original,
                cleaned,
                abbreviation,
                lookup.getStandardName(),
                lookup.getStandardCode(),
                lookup.getCategory(),
                1.0,
                matchSource
            );
        }

        return new CleanResult(
            original,
            cleaned,
            abbreviation,
            null,
            null,
            null,
            0.0,
            "unmatched"
        );
    }

    public static List<CleanResult> cleanBatch(List<String> itemNames, LookupProvider dictManager) {
        if (itemNames == null || itemNames.isEmpty()) {
            return Collections.emptyList();
        }
        List<CleanResult> results = new ArrayList<CleanResult>(itemNames.size());
        for (String itemName : itemNames) {
            results.add(clean(itemName, dictManager));
        }
        return results;
    }

    public static String cleanMajorItemName(String name) {
        String cleaned = strip(name);
        cleaned = fullWidthToHalfWidth(cleaned);
        if (cleaned.startsWith("H-")) {
            cleaned = cleaned.substring(2);
        }
        return strip(cleaned);
    }

    private static String strip(String name) {
        return name == null ? "" : name.trim();
    }

    private static String removeStarPrefix(String name) {
        String cleaned = name == null ? "" : name;
        while (cleaned.startsWith("★")) {
            cleaned = cleaned.substring(1);
        }
        return cleaned.trim();
    }

    private static String fullWidthToHalfWidth(String name) {
        if (name == null || name.isEmpty()) {
            return "";
        }
        StringBuilder builder = new StringBuilder(name.length());
        for (int i = 0; i < name.length(); i++) {
            char ch = name.charAt(i);
            switch (ch) {
                case '（':
                    builder.append('(');
                    break;
                case '）':
                    builder.append(')');
                    break;
                case '：':
                    builder.append(':');
                    break;
                case '，':
                    builder.append(',');
                    break;
                case '；':
                    builder.append(';');
                    break;
                case '【':
                    builder.append('[');
                    break;
                case '】':
                    builder.append(']');
                    break;
                case '！':
                    builder.append('!');
                    break;
                case '０':
                    builder.append('0');
                    break;
                case '１':
                    builder.append('1');
                    break;
                case '２':
                    builder.append('2');
                    break;
                case '３':
                    builder.append('3');
                    break;
                case '４':
                    builder.append('4');
                    break;
                case '５':
                    builder.append('5');
                    break;
                case '６':
                    builder.append('6');
                    break;
                case '７':
                    builder.append('7');
                    break;
                case '８':
                    builder.append('8');
                    break;
                case '９':
                    builder.append('9');
                    break;
                default:
                    builder.append(ch);
                    break;
            }
        }
        return builder.toString();
    }

    private static BracketResult extractAbbreviationFromBrackets(String name) {
        String normalized = name == null ? "" : name;
        Matcher matcher = BRACKET_ABBR_PATTERN.matcher(normalized);
        if (!matcher.matches()) {
            return new BracketResult(normalized, null);
        }
        return new BracketResult(rstrip(matcher.group(1)), matcher.group(2).trim());
    }

    private static String removeUnitSuffix(String name) {
        String normalized = name == null ? "" : name;
        Matcher matcher = UNIT_SUFFIX_PATTERN.matcher(normalized);
        if (!matcher.matches()) {
            return normalized;
        }
        String bracketContent = matcher.group(2).trim();
        if (UNIT_SUFFIXES.contains(bracketContent) || bracketContent.contains("/")) {
            return rstrip(matcher.group(1));
        }
        return normalized;
    }

    private static String removeTrailingPunctuation(String name) {
        return TRAILING_PUNCTUATION_PATTERN.matcher(name == null ? "" : name).replaceAll("");
    }

    private static String removeInternalSpaces(String name) {
        String previous = name == null ? "" : name;
        while (true) {
            String current = CHINESE_INTERNAL_SPACE_PATTERN.matcher(previous).replaceAll("$1$2");
            if (current.equals(previous)) {
                return current;
            }
            previous = current;
        }
    }

    private static String rstrip(String value) {
        if (value == null || value.isEmpty()) {
            return "";
        }
        int end = value.length();
        while (end > 0 && Character.isWhitespace(value.charAt(end - 1))) {
            end--;
        }
        return value.substring(0, end);
    }

    private static MapLookupProvider getDefaultLookupProvider() {
        MapLookupProvider provider = defaultLookupProvider;
        if (provider == null) {
            throw new IllegalStateException(
                "L1RuleCleaner has not been initialized. Call initializeOnce(projectRoot) during application startup."
            );
        }
        return provider;
    }

    private static List<Map<String, String>> readCsv(Path path) throws IOException {
        try (BufferedReader reader = Files.newBufferedReader(path, StandardCharsets.UTF_8)) {
            return readCsv(reader);
        }
    }

    private static List<Map<String, String>> readCsv(InputStream inputStream) throws IOException {
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(inputStream, StandardCharsets.UTF_8))) {
            return readCsv(reader);
        }
    }

    private static List<Map<String, String>> readCsv(BufferedReader reader) throws IOException {
        List<Map<String, String>> rows = new ArrayList<Map<String, String>>();
        String headerLine = reader.readLine();
        if (headerLine == null) {
            return rows;
        }

        List<String> headers = parseCsvLine(removeBom(headerLine));
        String line;
        while ((line = reader.readLine()) != null) {
            if (line.trim().isEmpty()) {
                continue;
            }
            List<String> values = parseCsvLine(line);
            Map<String, String> row = new HashMap<String, String>();
            for (int i = 0; i < headers.size(); i++) {
                String value = i < values.size() ? values.get(i) : "";
                row.put(headers.get(i), value);
            }
            rows.add(row);
        }
        return rows;
    }

    private static List<String> parseCsvLine(String line) {
        List<String> values = new ArrayList<String>();
        StringBuilder current = new StringBuilder();
        boolean inQuotes = false;

        for (int i = 0; i < line.length(); i++) {
            char ch = line.charAt(i);
            if (ch == '"') {
                if (inQuotes && i + 1 < line.length() && line.charAt(i + 1) == '"') {
                    current.append('"');
                    i++;
                } else {
                    inQuotes = !inQuotes;
                }
            } else if (ch == ',' && !inQuotes) {
                values.add(current.toString());
                current.setLength(0);
            } else {
                current.append(ch);
            }
        }

        values.add(current.toString());
        return values;
    }

    private static String removeBom(String value) {
        if (value != null && !value.isEmpty() && value.charAt(0) == '\uFEFF') {
            return value.substring(1);
        }
        return value;
    }

    private static List<String> splitAliases(String aliases) {
        if (isBlank(aliases)) {
            return Collections.emptyList();
        }
        List<String> result = new ArrayList<String>();
        String[] parts = aliases.split(";");
        for (String part : parts) {
            if (!isBlank(part)) {
                result.add(part.trim());
            }
        }
        return result;
    }

    private static boolean isBlank(String value) {
        return value == null || value.trim().isEmpty();
    }

    private static String trimToEmpty(String value) {
        return value == null ? "" : value.trim();
    }

    public interface LookupProvider {
        LookupPayload lookup(String cleanedName, String abbreviation);
    }

    public static final class MapLookupProvider implements LookupProvider {
        private final Map<String, LookupPayload> nameToCode = new HashMap<String, LookupPayload>();
        private final Map<String, LookupPayload> abbrToCode = new HashMap<String, LookupPayload>();
        private final Map<String, LookupPayload> nameUpperToCode = new HashMap<String, LookupPayload>();

        public void registerStandard(String standardName, String abbreviation, LookupPayload payload) {
            registerName(standardName, payload);
            if (abbreviation != null && !abbreviation.trim().isEmpty()) {
                String normalizedAbbr = abbreviation.trim().toUpperCase(Locale.ROOT);
                abbrToCode.put(normalizedAbbr, payload);
                nameUpperToCode.put(normalizedAbbr, payload);
            }
        }

        public void registerAlias(String alias, LookupPayload payload) {
            registerName(alias, payload);
        }

        private void registerName(String name, LookupPayload payload) {
            String normalized = name == null ? "" : name.trim();
            if (normalized.isEmpty() || payload == null) {
                return;
            }
            nameToCode.put(normalized, payload);
            nameUpperToCode.put(normalized.toUpperCase(Locale.ROOT), payload);
        }

        @Override
        public LookupPayload lookup(String cleanedName, String abbreviation) {
            String normalizedName = cleanedName == null ? "" : cleanedName.trim();
            LookupPayload payload = nameToCode.get(normalizedName);
            if (payload != null) {
                return payload;
            }

            if (abbreviation != null && !abbreviation.trim().isEmpty()) {
                payload = abbrToCode.get(abbreviation.trim().toUpperCase(Locale.ROOT));
                if (payload != null) {
                    return payload;
                }
            }

            return nameUpperToCode.get(normalizedName.toUpperCase(Locale.ROOT));
        }
    }

    public static final class LookupPayload {
        private final String standardCode;
        private final String standardName;
        private final String category;

        public LookupPayload(String standardCode, String standardName, String category) {
            this.standardCode = standardCode;
            this.standardName = standardName;
            this.category = category;
        }

        public String getStandardCode() {
            return standardCode;
        }

        public String getStandardName() {
            return standardName;
        }

        public String getCategory() {
            return category;
        }
    }

    public static final class CleanResult {
        private final String original;
        private final String cleaned;
        private final String abbreviation;
        private final String standardName;
        private final String standardCode;
        private final String category;
        private final double confidence;
        private final String matchSource;

        public CleanResult(
            String original,
            String cleaned,
            String abbreviation,
            String standardName,
            String standardCode,
            String category,
            double confidence,
            String matchSource
        ) {
            this.original = original;
            this.cleaned = cleaned;
            this.abbreviation = abbreviation;
            this.standardName = standardName;
            this.standardCode = standardCode;
            this.category = category;
            this.confidence = confidence;
            this.matchSource = matchSource;
        }

        public String getOriginal() {
            return original;
        }

        public String getCleaned() {
            return cleaned;
        }

        public String getAbbreviation() {
            return abbreviation;
        }

        public String getStandardName() {
            return standardName;
        }

        public String getStandardCode() {
            return standardCode;
        }

        public String getCategory() {
            return category;
        }

        public double getConfidence() {
            return confidence;
        }

        public String getMatchSource() {
            return matchSource;
        }

        @Override
        public String toString() {
            return "CleanResult{"
                + "original='" + original + '\''
                + ", cleaned='" + cleaned + '\''
                + ", abbreviation='" + abbreviation + '\''
                + ", standardName='" + standardName + '\''
                + ", standardCode='" + standardCode + '\''
                + ", category='" + category + '\''
                + ", confidence=" + confidence
                + ", matchSource='" + matchSource + '\''
                + '}';
        }
    }

    private static final class BracketResult {
        private final String cleanedName;
        private final String abbreviation;

        private BracketResult(String cleanedName, String abbreviation) {
            this.cleanedName = cleanedName;
            this.abbreviation = abbreviation;
        }
    }
}
