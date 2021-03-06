/*
 *
 * Copyright (C) 2016 Krishna Kuntala @ Mastek <krishna.kuntala@mastek.com>
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 * 
 * http://www.apache.org/licenses/LICENSE-2.0
 * 
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * 
 */
package com.dev.ops.common.thread.local;

import com.dev.ops.common.domain.ContextInfo;

public final class ContextThreadLocal {

	private static final ThreadLocal<ContextInfo> THREAD_LOCAL_CONTEXT_INFO = new ThreadLocal<ContextInfo>();

	private ContextThreadLocal() {
	}

	public static void set(final ContextInfo contextInfo) {
		THREAD_LOCAL_CONTEXT_INFO.set(contextInfo);
	}

	public static ContextInfo get() {
		return THREAD_LOCAL_CONTEXT_INFO.get();
	}

	public static void unset() {
		THREAD_LOCAL_CONTEXT_INFO.remove();
	}
}