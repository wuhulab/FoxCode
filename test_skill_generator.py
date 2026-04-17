#!/usr/bin/env python3
"""
测试技能生成器

验证 RuleBasedSkillGenerator 是否能正确根据规则文件生成技能
"""

import asyncio
from pathlib import Path
from foxcode.core.skill import skill_manager, register_builtin_skills, RuleBasedSkillGenerator, SkillContext

async def test_skill_generator():
    """测试技能生成器"""
    print("=== 测试技能生成器 ===")
    
    # 注册内置技能
    register_builtin_skills()
    
    # 查看初始技能列表
    initial_skills = skill_manager.list_skills()
    print(f"初始技能数量: {len(initial_skills)}")
    for skill in initial_skills:
        print(f"- {skill.name}: {skill.description}")
    
    # 创建技能生成器实例
    generator = RuleBasedSkillGenerator()
    
    # 测试执行技能生成
    context = SkillContext(user_input="生成技能")
    result = await generator.execute(context)
    
    print(f"\n技能生成结果: {result.success}")
    print(f"输出: {result.output}")
    if not result.success:
        print(f"错误: {result.error}")
        return
    
    # 查看生成后的技能列表
    generated_skills = skill_manager.list_skills()
    print(f"\n生成后技能数量: {len(generated_skills)}")
    
    # 打印新生成的技能
    print("\n新生成的技能:")
    for skill in generated_skills:
        if skill.name.startswith("rule-") or skill.name == "uop-coding-standard":
            print(f"- {skill.name}: {skill.description}")
    
    # 测试生成的技能是否能正确执行
    print("\n测试生成的技能执行:")
    for skill in generated_skills:
        if skill.name.startswith("rule-") or skill.name == "uop-coding-standard":
            print(f"\n执行技能: {skill.name}")
            result = await skill_manager.execute_skill(skill.name, context)
            print(f"执行结果: {result.success}")
            print(f"输出: {result.output}")

if __name__ == "__main__":
    asyncio.run(test_skill_generator())
