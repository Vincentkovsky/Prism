import React, { useState } from 'react';
import { ChevronDown, ChevronUp, Brain } from 'lucide-react';
import { ThoughtStep } from '../types';
import { MarkdownRenderer } from './MarkdownRenderer';

interface ThoughtProcessProps {
    steps: ThoughtStep[];
    isThinking?: boolean;
    defaultExpanded?: boolean;
}

export const ThoughtProcess: React.FC<ThoughtProcessProps> = ({
    steps,
    isThinking = false,
    defaultExpanded = false,
}) => {
    const [isExpanded, setIsExpanded] = useState(defaultExpanded);

    if (!steps.length && !isThinking) return null;

    return (
        <div className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden my-2">
            <button
                onClick={() => setIsExpanded(!isExpanded)}
                className="w-full flex items-center justify-between px-4 py-2 bg-gray-50 dark:bg-gray-800/50 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors text-sm font-medium text-gray-700 dark:text-gray-300"
            >
                <div className="flex items-center gap-2">
                    <Brain className="w-4 h-4 text-purple-500" />
                    <span>Thought Process</span>
                    <span className="text-xs text-gray-500 dark:text-gray-400 font-normal">
                        ({steps.length} step{steps.length !== 1 ? 's' : ''})
                    </span>
                </div>
                {isExpanded ? (
                    <ChevronUp className="w-4 h-4 text-gray-400" />
                ) : (
                    <ChevronDown className="w-4 h-4 text-gray-400" />
                )}
            </button>

            {isExpanded && (
                <div className="bg-white dark:bg-gray-900 divide-y divide-gray-100 dark:divide-gray-800">
                    {steps.map((step, index) => (
                        <div key={index} className="px-4 py-3 text-sm">
                            <div className="flex items-start gap-3">
                                <div className="flex-shrink-0 w-6 h-6 rounded-full bg-purple-100 dark:bg-purple-900/30 flex items-center justify-center text-xs font-bold text-purple-600 dark:text-purple-400 mt-0.5">
                                    {index + 1}
                                </div>
                                <div className="flex-1 space-y-2 min-w-0">
                                    {step.thought && (
                                        <div className="text-gray-600 dark:text-gray-300">
                                            <MarkdownRenderer content={step.thought} />
                                        </div>
                                    )}

                                    {step.action && (
                                        <div className="bg-gray-50 dark:bg-gray-800 rounded p-2 text-xs font-mono border border-gray-200 dark:border-gray-700">
                                            <div className="text-purple-600 dark:text-purple-400 font-semibold mb-1">
                                                Use Tool: {step.action}
                                            </div>
                                            <div className="text-gray-500 dark:text-gray-400 whitespace-pre-wrap break-words">
                                                {typeof step.actionInput === 'string'
                                                    ? step.actionInput
                                                    : JSON.stringify(step.actionInput, null, 2)}
                                            </div>
                                        </div>
                                    )}

                                    {step.observation && (
                                        <div className="text-gray-500 dark:text-gray-400 italic bg-blue-50/50 dark:bg-blue-900/10 p-2 rounded border-l-2 border-blue-400">
                                            <span className="font-semibold not-italic text-blue-600 dark:text-blue-400 text-xs uppercase tracking-wide block mb-1">
                                                Observation
                                            </span>
                                            <MarkdownRenderer content={step.observation} />
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>
                    ))}

                    {isThinking && (
                        <div className="px-4 py-3 text-sm flex items-center gap-3">
                            <div className="w-6 flex justify-center">
                                <div className="w-2 h-2 bg-purple-500 rounded-full animate-pulse" />
                            </div>
                            <span className="text-gray-400 italic">Thinking...</span>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};
