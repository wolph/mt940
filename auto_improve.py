#!/usr/bin/env python3
import argparse
import ast
import asyncio
import difflib
import logging
import os
import re
import sys
from datetime import datetime

import aiofiles
from openai import AsyncAzureOpenAI
from openai.types.chat import ChatCompletion
from rich.console import Console
from rich.layout import Layout
from rich.logging import RichHandler
from rich.panel import Panel
from rich.syntax import Syntax

PROMPT = """        
Please fix the following code to address all issues, ensuring that all public functions and classes from the original code are preserved.    
    
### Code Preservation    
- Do not remove any public or global functions, classes, or other global definitions, as they might be imported or used by other code.    
- Do not rename any functions or classes that could be used externally.    
- Do not remove any existing comments or docstrings.  
    
### Code Style    
- Adhere to PEP8 guidelines.    
- Limit lines to 79 characters.    
- Use single quotes `'` for strings instead of double quotes `"`.    
    
### Type Hinting    
- Use type hinting compatible with Python 3.13 and above:    
  - Use `list[T]` instead of `typing.List[T]`.    
  - Use `Union` types with the `|` operator (e.g., `int | None` instead of `typing.Optional[int]`).    
    
### Code Optimization    
- Split out functions where useful to reduce complexity.    
- Reuse code and variables where possible.    
- Optimize code for performance first and readability second.    
- Avoid using `global` variables.    
- Avoid using `eval()` and `exec()` functions.    
    
### Imports    
- Avoid using `from module import *`.    
- Import only the necessary functions or classes.    
- Prefer `import module` over `from module import function` when possible.    
    
### Documentation    
- Do not remove existing documentation or doctests.    
- Add documentation where it would be useful for an open-source public library.    
- Ensure every public function has documentation.    
- Do not remove links in the documentation.    
- Add doctests where useful.    
- Do not modify existing doctests.  
    
### Output Format    
Provide only the updated code for each file, enclosed within special markers as follows:    
    
For each file:        
<<FILE: file_path>>        
<code>        
<<ENDFILE>>        
Do not include any additional text or comments in the output.    
"""


async def main() -> None:
    """
    Main function to parse arguments and run the code improvement process.
    """
    console = Console()

    parser = argparse.ArgumentParser(
        description='Automatically improve Python files using Azure OpenAI API.'
    )
    parser.add_argument(
        'files', metavar='FILE', nargs='+', help='Python files to process'
    )
    parser.add_argument(
        '--max-iterations',
        type=int,
        default=1,
        help='Maximum number of iterations per file (default: 1)',
    )
    parser.add_argument(
        '--tools',
        nargs='+',
        choices=['ruff', 'pyright', 'mypy'],
        default=['ruff', 'pyright'],
        help='Specify code quality tools to run (default: ruff/pyright).',
    )
    parser.add_argument(
        '--verbose',
        '-v',
        action='store_true',
        help='Enable verbose logging',
    )
    parser.add_argument(
        '--force',
        '-f',
        action='store_true',
        help='Force write of files even with no improvements',
    )
    parser.add_argument(
        '--test',
        '-t',
        action='store_true',
        help='Run pytest after processing',
    )
    parser.add_argument(
        '--no-backup',
        '-B',
        action='store_true',
        help='Prevent the creation of backups before each step',
    )
    parser.add_argument(
        '--parallel-files',
        action='store_true',
        help='Process files individually and in parallel',
    )
    args = parser.parse_args()

    # Set up logging with color support
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(asctime)s %(name)s [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S',
        handlers=[RichHandler(rich_tracebacks=True)],
    )

    # Suppress logging from azure libraries
    logging.getLogger('azure').setLevel(logging.ERROR)
    logging.getLogger('openai').setLevel(logging.ERROR)
    logging.getLogger('httpcore').setLevel(logging.ERROR)

    # Environment variables
    azure_endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
    api_key = os.getenv('AZURE_OPENAI_API_KEY')
    openai_deployment = os.getenv('OPENAI_DEPLOYMENT')
    api_version = '2023-10-01-preview'  # Update to your API version if needed

    if not azure_endpoint or not api_key or not openai_deployment:
        logging.error(
            'Azure OpenAI environment variables are not set properly.'
        )
        sys.exit(1)

    # Set up Azure OpenAI API client
    client = AsyncAzureOpenAI(
        azure_endpoint=azure_endpoint,
        api_key=api_key,
        api_version=api_version,
    )

    # Read contents of all files
    original_code: dict[str, str] = {}
    for file_path in args.files:
        try:
            async with aiofiles.open(file_path) as f:
                original_code[file_path] = await f.read()
        except FileNotFoundError:
            logging.exception(f'File not found: {file_path}')
            sys.exit(1)
        except OSError as e:
            logging.exception(f'Error reading file {file_path}: {e}')
            sys.exit(1)

    # Run ruff format and fix on all files before processing
    for file_path in args.files:
        logging.info(f'Formatting {file_path} with ruff...')
        await run_ruff_format(file_path)
        await run_ruff_fix(file_path)

    async with client:
        # Process files based on the parallel_files flag
        await process_files(
            args.files,
            args.max_iterations,
            openai_deployment,
            args.tools,
            console,
            original_code,
            args.force,
            args.no_backup,
            client,
            args.parallel_files,
        )

    # Run ruff format and fix on all files after processing
    for file_path in args.files:
        logging.info(f'Formatting {file_path} with ruff...')
        await run_ruff_format(file_path)
        await run_ruff_fix(file_path)

    # Run pytest to verify that no code was broken if --test is specified
    if args.test:
        await run_pytest(console)


async def run_ruff_format(file_path: str) -> None:
    """
    Format the given file using ruff format.

    Args:
        file_path (str): Path to the file to format.
    """
    try:
        process = await asyncio.create_subprocess_exec(
            'ruff',
            'format',
            file_path,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await process.communicate()
    except OSError as e:
        logging.exception(f'Error running ruff format on {file_path}: {e}')


async def run_ruff_fix(file_path: str) -> None:
    """
    Fix the given file using ruff fix.

    Args:
        file_path (str): Path to the file to fix.
    """
    try:
        process = await asyncio.create_subprocess_exec(
            'ruff',
            'check',
            '--fix',
            file_path,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await process.communicate()
    except OSError as e:
        logging.exception(f'Error running ruff fix on {file_path}: {e}')


async def process_files(
    file_paths: list[str],
    max_iterations: int,
    model: str,
    tools: list[str],
    console: Console,
    original_code: dict[str, str],
    force_write: bool,
    no_backup: bool,
    client: AsyncAzureOpenAI,
    parallel_files: bool,
) -> None:
    """
    Process the files, improving their code with the help of OpenAI.

    Args:
        file_paths (list[str]): List of file paths to process.
        max_iterations (int): Maximum number of iterations to attempt improvements.
        model (str): Deployment ID for the Azure OpenAI service.
        tools (list[str]): List of code quality tools to use.
        console (Console): Rich console instance for output.
        original_code (dict[str, str]): Original code for each file.
        force_write (bool): Whether to write files even if there are no improvements.
        no_backup (bool): Whether to skip creating backups before writing files.
        client (AsyncAzureOpenAI): The async Azure OpenAI client.
        parallel_files (bool): Whether to process files individually and in parallel.
    """
    if parallel_files:
        # Process files individually and in parallel
        tasks = [
            process_single_file(
                file_path,
                max_iterations,
                model,
                tools,
                console,
                original_code[file_path],
                force_write,
                no_backup,
                client,
            )
            for file_path in file_paths
        ]
        await asyncio.gather(*tasks)
    else:
        # Process files together
        code_to_improve = original_code.copy()
        improved_code = code_to_improve.copy()

        for iteration in range(1, max_iterations + 1):
            print(f'Iteration {iteration} of {max_iterations}: {file_paths}')
            logging.info(f'Iteration {iteration} of {max_iterations}')
            logging.info('Improving code using %s', model)

            # Run code quality tools on current code
            logging.info('Running code quality tools before improvement...')

            # Write code_to_improve to temporary files
            temp_files = []
            for file_path in file_paths:
                temp_file_path = file_path + '.temp.before'
                temp_files.append(temp_file_path)
                async with aiofiles.open(temp_file_path, 'w') as f:
                    await f.write(code_to_improve[file_path])

            quality_errors = await run_quality_tools(temp_files, tools)

            # Remove temporary files
            for temp_file in temp_files:
                if os.path.exists(temp_file):
                    os.remove(temp_file)

            if quality_errors:
                logging.info('Current code quality issues:')
                logging.info(quality_errors)
            else:
                logging.info('No code quality issues in current code.')

            # If no quality errors, and no improvements, and force_write is not set, stop further iterations
            if not quality_errors.strip():
                logging.info('No code quality issues found.')
                unchanged = all(
                    improved_code[fp] == original_code[fp] for fp in file_paths
                )
                if unchanged and not force_write:
                    logging.info('No changes made to the code.')
                    break

                # Process improved_code vs original_code
                for file_path in file_paths:
                    if (
                        improved_code[file_path] != original_code[file_path]
                        or force_write
                    ):
                        # Verify globals before writing
                        missing_globals_error = check_global_definitions(
                            original_code[file_path],
                            improved_code[file_path],
                        )
                        if missing_globals_error:
                            logging.error(
                                f'Globals missing in the improved code for {file_path}:'
                            )
                            logging.error(missing_globals_error)
                            logging.error(
                                f'Aborting write operation for {file_path} due to missing globals.'
                            )
                            if not force_write:
                                continue  # Skip writing this file

                        # Create backup if not --no-backup
                        if not no_backup:
                            backup_file_path = os.path.join(
                                os.path.dirname(file_path),
                                f'{datetime.now()}.{os.path.basename(file_path)}',
                            )
                            logging.info(
                                f'Creating backup of {file_path} at {backup_file_path}'
                            )
                            async with aiofiles.open(
                                backup_file_path, 'w'
                            ) as f:
                                await f.write(original_code[file_path])

                        # Show diff and write improved code
                        show_diff_with_syntax_highlighting(
                            console,
                            original_code[file_path],
                            improved_code[file_path],
                            file_path,
                        )
                        logging.info(
                            f'Writing improved code to original file {file_path}...'
                        )
                        async with aiofiles.open(file_path, 'w') as f:
                            await f.write(improved_code[file_path])
                        logging.info(
                            f'No errors found in {file_path} after {iteration} iteration(s).'
                        )
                    else:
                        logging.info(
                            f'No changes made to the code in {file_path}.'
                        )
                break

            # Improve the code using OpenAI API
            print('Improving code... {file_paths}')
            improved_code_text = await process_code_with_openai(
                code_to_improve,
                model,
                client,
                quality_errors=quality_errors,
                mode='improve',
            )

            # Parse improved_code_text to get improved_code per file
            improved_code = parse_improved_code(
                improved_code_text, file_paths, code_to_improve
            )

            # Check if improved_code is unchanged
            unchanged = all(
                improved_code[fp] == code_to_improve[fp] for fp in file_paths
            )

            if unchanged:
                logging.error('Failed to improve code. Exiting iteration.')
                break

            # Check for missing global definitions
            logging.info('Checking for missing global definitions...')
            globals_errors = ''
            for file_path in file_paths:
                missing_globals_error = check_global_definitions(
                    original_code[file_path], improved_code[file_path]
                )
                if missing_globals_error:
                    logging.error(
                        f'Globals missing in the improved code for {file_path}:'
                    )
                    logging.error(missing_globals_error)
                    globals_errors += missing_globals_error + '\n'
                else:
                    logging.info(
                        f'All global definitions are present in {file_path}.'
                    )

            # Check for missing public definitions
            logging.info('Checking for missing public definitions...')
            errors = ''
            for file_path in file_paths:
                missing_defs_error = check_public_definitions(
                    original_code[file_path], improved_code[file_path]
                )
                if missing_defs_error:
                    logging.warning(
                        f'Public definitions missing in {file_path}:'
                    )
                    logging.warning(missing_defs_error)
                    errors += missing_defs_error + '\n'
                else:
                    logging.info(
                        f'All public definitions are present in {file_path}.'
                    )

            errors += globals_errors

            # Save the improved code to temporary files
            temp_files = []
            for file_path in file_paths:
                temp_file_path = file_path + '.temp'
                temp_files.append(temp_file_path)
                async with aiofiles.open(temp_file_path, 'w') as f:
                    await f.write(improved_code[file_path])

            # Run code quality tools on the temp files
            logging.info('Running code quality tools after improvement...')
            quality_errors = await run_quality_tools(temp_files, tools)
            if quality_errors:
                logging.warning('Code quality issues found:')
                logging.warning(quality_errors)
                errors += quality_errors
            else:
                logging.info('No code quality issues found after improvement.')

                # Verify globals before writing
                all_globals_present = True
                for file_path in file_paths:
                    missing_globals_error = check_global_definitions(
                        original_code[file_path], improved_code[file_path]
                    )
                    if missing_globals_error:
                        logging.error(
                            f'Globals missing in the improved code for {file_path}:'
                        )
                        logging.error(missing_globals_error)
                        logging.error(
                            f'Aborting write operation for {file_path} due to missing globals.'
                        )
                        all_globals_present = False
                        break

                if not all_globals_present and not force_write:
                    # Proceed to next iteration to fix the missing globals
                    code_to_improve = improved_code.copy()
                    continue

                # Show diff and write improved code
                for file_path in file_paths:
                    if (
                        improved_code[file_path] != original_code[file_path]
                        or force_write
                    ):
                        # Create backup if not --no-backup
                        if not no_backup:
                            backup_file_path = os.path.join(
                                os.path.dirname(file_path),
                                f'{datetime.now()}.{os.path.basename(file_path)}',
                            )
                            logging.info(
                                f'Creating backup of {file_path} at '
                                f'{backup_file_path}'
                            )
                            async with aiofiles.open(
                                backup_file_path, 'w'
                            ) as f:
                                await f.write(original_code[file_path])

                        show_diff_with_syntax_highlighting(
                            console,
                            original_code[file_path],
                            improved_code[file_path],
                            file_path,
                        )
                        logging.info(
                            'Writing improved code to original file '
                            f'{file_path}...'
                        )
                        async with aiofiles.open(file_path, 'w') as f:
                            await f.write(improved_code[file_path])
                        logging.info(
                            f'No errors found in {file_path} after '
                            f'{iteration} iteration(s).'
                        )

                # Remove temporary files
                for temp_file in temp_files:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                break

            # Provide the errors to the assistant to fix the code
            logging.info('Fixing code based on errors...')
            code_to_improve_text = await process_code_with_openai(
                improved_code,
                model,
                client,
                errors=errors,
                mode='fix',
            )

            # Parse code_to_improve_text to get code_to_improve per file
            code_to_improve = parse_improved_code(
                code_to_improve_text, file_paths, improved_code
            )

            # Check if code_to_improve is unchanged
            unchanged = all(
                code_to_improve[fp] == improved_code[fp] for fp in file_paths
            )

            if unchanged:
                logging.error('Failed to fix code. Exiting iteration.')
                break

            # Remove temporary files
            for temp_file in temp_files:
                if os.path.exists(temp_file):
                    os.remove(temp_file)

        else:
            logging.warning(
                f'Maximum iterations ({max_iterations}) reached. Errors may remain.'
            )
            # Optionally, show diff and write last improved code
            for file_path in file_paths:
                if (
                    improved_code[file_path] != original_code[file_path]
                    or force_write
                ):
                    # Create backup if not --no-backup
                    if not no_backup:
                        backup_file_path = os.path.join(
                            os.path.dirname(file_path),
                            f'{datetime.now()}.{os.path.basename(file_path)}',
                        )
                        logging.info(
                            f'Creating backup of {file_path} at '
                            f'{backup_file_path}'
                        )
                        async with aiofiles.open(backup_file_path, 'w') as f:
                            await f.write(original_code[file_path])

                    show_diff_with_syntax_highlighting(
                        console,
                        original_code[file_path],
                        improved_code[file_path],
                        file_path,
                    )
                    logging.info(
                        f'Writing last improved code to original file {file_path}.'
                    )

                    # Verify globals before writing
                    missing_globals_error = check_global_definitions(
                        original_code[file_path], improved_code[file_path]
                    )
                    if missing_globals_error and not force_write:
                        logging.error(
                            f'Globals missing in the improved code for {file_path}:'
                        )
                        logging.error(missing_globals_error)
                        logging.error(
                            f'Aborting write operation for {file_path} due to missing globals.'
                        )
                        continue  # Skip writing this file

                    async with aiofiles.open(file_path, 'w') as f:
                        await f.write(improved_code[file_path])
            # Remove temporary files if they exist
            for temp_file in temp_files:
                if os.path.exists(temp_file):
                    os.remove(temp_file)


async def process_single_file(
    file_path: str,
    max_iterations: int,
    model: str,
    tools: list[str],
    console: Console,
    original_code: str,
    force_write: bool,
    no_backup: bool,
    client: AsyncAzureOpenAI,
) -> None:
    """
    Process a single file, improving its code with the help of OpenAI.

    Args:
        file_path (str): Path to the file to process.
        max_iterations (int): Maximum number of iterations to attempt improvements.
        model (str): Deployment ID for the Azure OpenAI service.
        tools (list[str]): List of code quality tools to use.
        console (Console): Rich console instance for output.
        original_code (str): Original code for the file.
        force_write (bool): Whether to write files even if there are no improvements.
        no_backup (bool): Whether to skip creating backups before writing files.
        client (AsyncAzureOpenAI): The async Azure OpenAI client.
    """
    code_to_improve = original_code
    improved_code = code_to_improve

    for iteration in range(1, max_iterations + 1):
        print(f'Iteration {iteration} of {max_iterations}: {file_path}')
        logging.info(
            f'Processing {file_path} - Iteration {iteration} of {max_iterations}'
        )
        logging.info('Improving code using %s', model)

        # Run code quality tools on current code
        logging.info(
            f'Running code quality tools on {file_path} before improvement...'
        )
        temp_file_path = file_path + '.temp.before'
        async with aiofiles.open(temp_file_path, 'w') as f:
            await f.write(code_to_improve)
        quality_errors = await run_quality_tools([temp_file_path], tools)
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

        if quality_errors:
            logging.info('Current code quality issues:')
            logging.info(quality_errors)
        else:
            logging.info('No code quality issues in current code.')

        # If no quality errors, and no improvements, and force_write is not set, stop further iterations
        if not quality_errors.strip():
            logging.info('No code quality issues found.')
            if improved_code == original_code and not force_write:
                logging.info('No changes made to the code.')
                break

            # Verify globals before writing
            missing_globals_error = check_global_definitions(
                original_code, improved_code
            )
            if missing_globals_error:
                logging.error(
                    f'Globals missing in the improved code for {file_path}:'
                )
                logging.error(missing_globals_error)
                logging.error(
                    f'Aborting write operation for {file_path} due to missing globals.'
                )
                if not force_write:
                    continue  # Skip writing this file

            # Create backup if not --no-backup
            if not no_backup:
                backup_file_path = os.path.join(
                    os.path.dirname(file_path),
                    f'{datetime.now()}.{os.path.basename(file_path)}',
                )
                logging.info(
                    f'Creating backup of {file_path} at {backup_file_path}'
                )
                async with aiofiles.open(backup_file_path, 'w') as f:
                    await f.write(original_code)

            # Show diff and write improved code
            show_diff_with_syntax_highlighting(
                console,
                original_code,
                improved_code,
                file_path,
            )
            logging.info(
                f'Writing improved code to original file {file_path}...'
            )
            async with aiofiles.open(file_path, 'w') as f:
                await f.write(improved_code)
            logging.info(
                f'No errors found in {file_path} after {iteration} iteration(s).'
            )
            break

        # Improve the code using OpenAI API
        print('Improving code... {file_path}')
        improved_code_text = await process_code_with_openai(
            {file_path: code_to_improve},
            model,
            client,
            quality_errors=quality_errors,
            mode='improve',
        )

        # Parse improved_code_text to get improved_code
        improved_code_dict = parse_improved_code(
            improved_code_text, [file_path], {file_path: code_to_improve}
        )
        improved_code = improved_code_dict[file_path]

        # Check if improved_code is unchanged
        if improved_code == code_to_improve:
            logging.error('Failed to improve code. Exiting iteration.')
            break

        # Check for missing global definitions
        logging.info('Checking for missing global definitions...')
        missing_globals_error = check_global_definitions(
            original_code, improved_code
        )
        if missing_globals_error:
            logging.error(
                f'Globals missing in the improved code for {file_path}:'
            )
            logging.error(missing_globals_error)
            globals_errors = missing_globals_error + '\n'
        else:
            logging.info(f'All global definitions are present in {file_path}.')
            globals_errors = ''

        # Check for missing public definitions
        logging.info('Checking for missing public definitions...')
        missing_defs_error = check_public_definitions(
            original_code, improved_code
        )
        if missing_defs_error:
            logging.warning(f'Public definitions missing in {file_path}:')
            logging.warning(missing_defs_error)
            errors = missing_defs_error + '\n' + globals_errors
        else:
            logging.info(f'All public definitions are present in {file_path}.')
            errors = globals_errors

        # Save the improved code to temporary file
        temp_file_path = file_path + '.temp'
        async with aiofiles.open(temp_file_path, 'w') as f:
            await f.write(improved_code)

        # Run code quality tools on the temp file
        logging.info(
            f'Running code quality tools on {file_path} after improvement...'
        )
        quality_errors = await run_quality_tools([temp_file_path], tools)
        if quality_errors:
            logging.warning('Code quality issues found:')
            logging.warning(quality_errors)
            errors += quality_errors
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

        if not errors.strip():
            # Verify globals before writing
            missing_globals_error = check_global_definitions(
                original_code, improved_code
            )
            if missing_globals_error and not force_write:
                logging.error(
                    f'Globals missing in the improved code for {file_path}:'
                )
                logging.error(missing_globals_error)
                logging.error(
                    f'Aborting write operation for {file_path} due to missing globals.'
                )
                continue  # Skip writing this file

            # Create backup if not --no-backup
            if not no_backup:
                backup_file_path = os.path.join(
                    os.path.dirname(file_path),
                    f'{datetime.now()}.{os.path.basename(file_path)}',
                )
                logging.info(
                    f'Creating backup of {file_path} at ' f'{backup_file_path}'
                )
                async with aiofiles.open(backup_file_path, 'w') as f:
                    await f.write(original_code)

            # Show diff and write improved code
            show_diff_with_syntax_highlighting(
                console,
                original_code,
                improved_code,
                file_path,
            )
            logging.info(
                'Writing improved code to original file ' f'{file_path}...'
            )
            async with aiofiles.open(file_path, 'w') as f:
                await f.write(improved_code)
            logging.info(
                f'No errors found in {file_path} after '
                f'{iteration} iteration(s).'
            )

            break
        # Provide the errors to the assistant to fix the code
        logging.info(f'Fixing code for {file_path} based on errors...')
        code_to_improve_text = await process_code_with_openai(
            {file_path: improved_code},
            model,
            client,
            errors=errors,
            mode='fix',
        )

        # Parse code_to_improve_text to get code_to_improve
        code_to_improve_dict = parse_improved_code(
            code_to_improve_text,
            [file_path],
            {file_path: improved_code},
        )
        code_to_improve = code_to_improve_dict[file_path]

        # Check if code_to_improve is unchanged
        if code_to_improve == improved_code:
            logging.error('Failed to fix code. Exiting iteration.')
            break

        # Update improved_code for next iteration
        improved_code = code_to_improve

    else:
        logging.warning(
            f'Maximum iterations ({max_iterations}) reached for {file_path}. Errors may remain.'
        )
        # Optionally, show diff and write last improved code
        if improved_code != original_code or force_write:
            # Create backup if not --no-backup
            if not no_backup:
                backup_file_path = os.path.join(
                    os.path.dirname(file_path),
                    f'{datetime.now()}.{os.path.basename(file_path)}',
                )
                logging.info(
                    f'Creating backup of {file_path} at {backup_file_path}'
                )
                async with aiofiles.open(backup_file_path, 'w') as f:
                    await f.write(original_code)

            show_diff_with_syntax_highlighting(
                console, original_code, improved_code, file_path
            )
            logging.info(
                f'Writing last improved code to original file {file_path}.'
            )
            # Verify globals before writing
            missing_globals_error = check_global_definitions(
                original_code, improved_code
            )
            if missing_globals_error and not force_write:
                logging.error(
                    f'Globals missing in the improved code for {file_path}:'
                )
                logging.error(missing_globals_error)
                logging.error(
                    f'Aborting write operation for {file_path} due to missing globals.'
                )
            else:
                async with aiofiles.open(file_path, 'w') as f:
                    await f.write(improved_code)


def parse_improved_code(
    response_text: str, file_paths: list[str], fallback_code: dict[str, str]
) -> dict[str, str]:
    """
    Parses the assistant's response to extract improved code for each file.

    Args:
        response_text (str): The response text from the assistant.
        file_paths (list[str]): List of file paths.
        fallback_code (dict[str, str]): Original code to fallback on if
        parsing fails.

    Returns:
        dict[str, str]: Dictionary mapping file paths to improved code.
    """
    improved_code: dict[str, str] = {}
    pattern = r'<<FILE:(.*?)>>(.*?)<<ENDFILE>>'
    matches = re.findall(pattern, response_text, re.DOTALL)
    for file_name, code in matches:
        file_name = file_name.strip()
        code = code.strip()
        if file_name in file_paths:
            improved_code[file_name] = code
        else:
            logging.warning(
                f'Received code for unexpected file {file_name}. Ignoring.'
            )

    # Check if any files are missing from the response
    for file_path in file_paths:
        if file_path not in improved_code:
            logging.warning(
                f"No improved code for {file_path} found in the assistant's"
                f' response.'
            )
            improved_code[file_path] = fallback_code[file_path]

    return improved_code


def show_diff_with_syntax_highlighting(
    console: Console, original_code: str, improved_code: str, file_path: str
) -> None:
    """
    Shows a syntax-highlighted diff between the original and improved code.

    Args:
        console (Console): Rich console instance for output.
        original_code (str): The original code.
        improved_code (str): The improved code.
        file_path (str): The path to the file.
    """
    logging.info(
        f'Showing diff between original and improved code for {file_path}:'
    )
    diff = list(
        difflib.unified_diff(
            original_code.splitlines(),
            improved_code.splitlines(),
            fromfile=f'Original {file_path}',
            tofile=f'Improved {file_path}',
            lineterm='',
        )
    )
    if diff:
        original_syntax = Syntax(
            original_code, 'python', line_numbers=True, word_wrap=True
        )
        improved_syntax = Syntax(
            improved_code, 'python', line_numbers=True, word_wrap=True
        )
        layout = Layout()
        layout.split_row(
            Layout(Panel(original_syntax, title=f'Original {file_path}')),
            Layout(Panel(improved_syntax, title=f'Improved {file_path}')),
        )
        console.print(layout)
    else:
        logging.info(
            f'No differences found between original and improved code for '
            f'{file_path}.'
        )


async def process_code_with_openai(
    code_dict: dict[str, str],
    model: str,
    client: AsyncAzureOpenAI,
    errors: str = '',
    quality_errors: str = '',
    mode: str = 'improve',  # 'improve' or 'fix'
) -> str:
    """
    Use OpenAI API to improve or fix code for multiple files based on errors.

    Args:
        code_dict (dict[str, str]): Dictionary mapping file paths to code.
        model (str): Deployment ID for the Azure OpenAI service.
        client (AsyncAzureOpenAI): The async Azure OpenAI client.
        errors (str): String containing code errors to address.
        quality_errors (str): String containing code quality errors.
        mode (str): Mode of operation, 'improve' or 'fix'.

    Returns:
        str: Improved or fixed code as a string with markers indicating files.
    """
    # Build the base prompt
    base_prompt = PROMPT.strip()

    prompt = base_prompt

    if mode == 'improve':
        # Add the code quality errors
        prompt += '\n\nHere are the code quality issues found by ruff and '
        prompt += 'pyright (if any):\n'
        prompt += quality_errors or 'No issues found.'
        prompt += '\n\nOriginal code for all files:\n'
    elif mode == 'fix':
        # Add the specific errors
        prompt += '\n\nHere are the errors:\n'
        prompt += errors
        prompt += '\n\nHere is the code that needs fixing:\n'

    # Add the code for all files
    for file_path, code in code_dict.items():
        prompt += f'\n<<FILE: {file_path}>>\n{code}\n<<ENDFILE>>'

    messages = [
        {'role': 'user', 'content': prompt},
    ]

    logging.debug(f'Sending {mode} request to OpenAI API...')

    try:
        # Use the client's acompletion method
        response: ChatCompletion = await client.chat.completions.create(
            messages=messages,
            model=model,
        )
    except Exception:
        logging.exception('Azure OpenAI API error')
        return '\n'.join(code_dict.values())  # Return the original code

    code_text = response.choices[0].message.content
    logging.info('Usage statistics: %r', response.usage)
    logging.debug(f'Received {mode} response from OpenAI API')
    logging.debug('Code received:')
    logging.debug(code_text)

    return code_text


async def run_quality_tools(file_paths: list[str], tools: list[str]) -> str:
    """
    Runs code quality tools on the given files and collects errors.

    Args:
        file_paths (list[str]): List of file paths to check.
        tools (list[str]): List of tools to use ('ruff', 'pyright', 'mypy').

    Returns:
        str: Combined error messages from all tools.
    """
    errors = ''
    tasks = []

    for file_path in file_paths:
        if 'ruff' in tools:
            logging.debug(f'Running ruff on {file_path}...')
            tasks.append(
                run_tool(
                    'ruff',
                    ['check', '--fix', file_path],
                    f'Ruff errors in {file_path}:\n',
                )
            )
        if 'pyright' in tools:
            logging.debug(f'Running pyright on {file_path}...')
            tasks.append(
                run_tool(
                    'pyright', [file_path], f'Pyright errors in {file_path}:\n'
                )
            )
        if 'mypy' in tools:
            logging.debug(f'Running mypy on {file_path}...')
            tasks.append(
                run_tool('mypy', [file_path], f'Mypy errors in {file_path}:\n')
            )

    # Run all tasks concurrently
    results = await asyncio.gather(*tasks)
    # Collect errors
    errors = '\n'.join(r for r in results if r)
    return errors.strip()


async def run_tool(tool_name: str, args: list[str], error_prefix: str) -> str:
    """
    Run a code quality tool and capture its output.

    Args:
        tool_name (str): Name of the tool to run (e.g., 'ruff', 'pyright', 'mypy').
        args (list[str]): List of arguments to pass to the tool.
        error_prefix (str): Prefix to include in the error messages.

    Returns:
        str: Captured errors from the tool's output.
    """
    try:
        process = await asyncio.create_subprocess_exec(
            tool_name,
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_bytes, stderr_bytes = await process.communicate()
        returncode = process.returncode
    except OSError as e:
        logging.exception(f'Error running {tool_name}')
        return f'{error_prefix}Error running {tool_name}: {e}\n'

    # Decode outputs
    stdout = (
        stdout_bytes.decode('utf-8', errors='replace') if stdout_bytes else ''
    )
    stderr = (
        stderr_bytes.decode('utf-8', errors='replace') if stderr_bytes else ''
    )

    errors = ''
    if tool_name == 'ruff':
        if returncode != 0:
            errors = error_prefix + stdout + stderr + '\n'
    elif tool_name == 'pyright':
        if stdout and not stdout.strip().endswith(
            '0 errors, 0 warnings, 0 infos'
        ):
            errors = error_prefix + stdout + stderr + '\n'
    elif tool_name == 'mypy' and (returncode != 0 or stdout or stderr):
        errors = error_prefix + stdout + stderr + '\n'
    return errors


def extract_global_definitions(code: str) -> set[str]:
    """
    Extracts the names of all global functions and classes from code.

    Args:
        code (str): The code to analyze.

    Returns:
        set[str]: Set of global function and class names.
    """
    global_defs: set[str] = set()
    try:
        tree = ast.parse(code)
    except SyntaxError:
        logging.exception('Syntax error during AST parsing')
        return global_defs

    for node in tree.body:
        if isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            global_defs.add(node.name)

    return global_defs


def check_global_definitions(original_code: str, improved_code: str) -> str:
    """
    Checks that all global functions and classes from the original code exist
    in the improved code.

    Returns an error message if any are missing.

    Args:
        original_code (str): The original code.
        improved_code (str): The improved code.

    Returns:
        str: Error message if globals are missing; empty string otherwise.
    """
    original_globals = extract_global_definitions(original_code)
    improved_globals = extract_global_definitions(improved_code)
    missing_globals = original_globals - improved_globals
    if missing_globals:
        return (
            'The following global functions or classes are missing in the '
            'improved code:\n'
            + '\n'.join(sorted(missing_globals))
            + '\nPlease ensure that all global functions and classes from the '
            'original code are preserved.'
        )
    return ''


def extract_public_definitions_with_parents(code: str) -> set[str]:
    """
    Extracts the names of public functions and classes from the code,
    considering their parent scopes.

    Args:
        code (str): The code to analyze.

    Returns:
        set[str]: Set of names of public functions and classes with parent
        scopes.
    """
    public_defs: set[str] = set()
    try:
        tree = ast.parse(code)
        add_parent_pointers(tree)
    except SyntaxError:
        logging.exception('Syntax error during AST parsing')
        return public_defs

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            names = [node.name]
            parent = getattr(node, 'parent', None)
            while parent and not isinstance(parent, ast.Module):
                if isinstance(parent, (ast.ClassDef, ast.FunctionDef)):
                    names.append(parent.name)
                parent = getattr(parent, 'parent', None)
            full_name = '.'.join(reversed(names))
            if not node.name.startswith('_'):
                public_defs.add(full_name)

    return public_defs


def check_public_definitions(original_code: str, improved_code: str) -> str:
    """
    Checks that all public functions and classes from the original code exist
    in the improved code.

    Returns an error message if any are missing.

    Args:
        original_code (str): The original code.
        improved_code (str): The improved code.

    Returns:
        str: Error message if public definitions are missing; empty string
        otherwise.
    """
    original_defs = extract_public_definitions_with_parents(original_code)
    improved_defs = extract_public_definitions_with_parents(improved_code)
    missing_defs = original_defs - improved_defs
    if missing_defs:
        return (
            'The following public functions or classes are missing in the '
            'improved code:\n'
            + '\n'.join(sorted(missing_defs))
            + '\nPlease ensure that all public functions and classes from the '
            'original code are preserved.'
        )
    return ''


def add_parent_pointers(tree: ast.AST) -> None:
    """
    Modify AST nodes to keep track of parent nodes.

    Args:
        tree (ast.AST): The AST tree to modify.
    """
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            child.parent = node


async def run_pytest(console: Console) -> None:
    """
    Runs pytest to verify that the code changes did not break any tests.

    Args:
        console (Console): Rich console instance for output.
    """
    logging.info('Running pytest to verify that no code was broken...')
    try:
        process = await asyncio.create_subprocess_exec(
            'pytest',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout_bytes, _ = await process.communicate()
        stdout = stdout_bytes.decode('utf-8', errors='replace')
        if process.returncode == 0:
            logging.info('All tests passed successfully.')
        else:
            logging.error('Tests failed. Please check the output below:')
            console.print(stdout)
    except OSError:
        logging.exception('Error running pytest')
    except Exception:
        logging.exception('Unexpected error running pytest')


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info('Process interrupted by user.')
